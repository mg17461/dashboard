from django.shortcuts import render, redirect
import re
from ladybug.futil import preparedir, nukedir
from .forms import EPWUploadForm
from .forms import CatchmentAreaForm
from .forms import PVToolForm
from .models import EPWFile
import json
from honeybee_energy.cli.simulate import simulate_model
from honeybee.typing import clean_ep_string
from honeybee_energy.run import to_openstudio_osw, run_osw, run_idf, output_energyplus_files
from honeybee_energy.result.generation import generation_data_from_sql, generation_summary_from_sql
from honeybee_energy.simulation.parameter import SimulationParameter
import math
# Import Ladybug Tools for analysis
from ladybug.epw import EPW
import sys
from honeybee.room import Room
from lbt_recipes.version import check_openstudio_version
from honeybee.model import Model
from ladybug_geometry.geometry3d import Vector3D, Point3D
from honeybee.shade import Shade
from honeybee_energy.generator.pv import PVProperties
#from honeybee_energy.run import RunEnergySimulation
from honeybee_vtk.model import Model as ModelVTK
import os
from django.conf import settings  # Add this import at the top of your views.py
#import openmeteo_requests
#import requests_cache
import pandas as pd
import shutil
#from retry_requests import retry

import numpy as np
import matplotlib
import seaborn as sns

import base64
matplotlib.use('Agg')  # Set the backend to 'Agg'
import matplotlib.pyplot as plt
from io import BytesIO


def home(request):
    if request.method == 'POST':
        form = EPWUploadForm(request.POST, request.FILES)
        if form.is_valid():
            epw_instance = form.save()  # Saves the EPW file instance
            epw_data = EPW(epw_instance.file.path)
            location = epw_data.location

            # Store necessary information in the session
            request.session['epw_file_id'] = epw_instance.id
            request.session['epw_file_location'] = f"{location.city}, {location.country}"
            request.session['epw_file_lat'] = location.latitude
            request.session['epw_file_long'] = location.longitude

            return redirect('weather_stats')
    else:
        form = EPWUploadForm()

    return render(request, 'firstapp/home.html', {'form': form})

def reset_epw_session(request):
    # List all session keys related to EPW data
    session_keys = ['epw_file_id', 'epw_file_location', 'epw_file_lat', 'epw_file_long']
    for key in session_keys:
        if key in request.session:
            del request.session[key]
    return redirect('home')


def extract_lat_long_from_epw(epw_file):
    # Implement the logic to extract latitude and longitude from the EPW file here
    # Placeholder return values
    return 52.52, 13.41

def weather_stats(request):
    context = {'active_page': 'weather_stats'}  # Initialize context with form and active_page
    epw_file_id = request.session.get('epw_file_id')

    if epw_file_id:
        try:
            epw_file_model = EPWFile.objects.get(id=epw_file_id)
            epw_file_path = epw_file_model.file.path
            epw_data = EPW(epw_file_path)

            monthly_averages = []
            monthly_mins = []
            monthly_maxs = []

            #HourlyContinuousCollection from epw file
            dry_bulb_temp = epw_data.dry_bulb_temperature
            print(dry_bulb_temp)

            #monthly_averages = dry_bulb_temp.average_monthly()
            grouped = dry_bulb_temp.group_by_month()

            for month, temps in grouped.items():
                monthly_averages.append(np.mean(temps))
                monthly_mins.append(np.min(temps))
                monthly_maxs.append(np.max(temps))

            # Ensure using the non-GUI backend for matplotlib
            matplotlib.use('Agg')

            # Set the Seaborn theme for nicer aesthetics
            sns.set_theme()

            # Generate a list of months (assuming 1 to 12 for simplicity)
            months = list(range(1, 13))

            # Plotting
            plt.figure(figsize=(10, 6))

            # Use fill_between to show the range between monthly minimum and maximum temperatures
            plt.fill_between(months, monthly_mins, monthly_maxs, color='lightblue', alpha=0.4, label='Min-Max Range')

            # Plot the monthly averages
            plt.plot(months, monthly_averages, label='Monthly Average', color='red', marker='o', linestyle='-')

            # Adding labels and title
            plt.xticks(months, ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
            plt.xlabel('Month')
            plt.ylabel('Temperature (°C)')
            plt.title('Monthly Temperature Statistics')
            plt.legend()

            plt.tight_layout()

            # Save the plot to a BytesIO buffer
            buf = BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            plt.close()
            buf.seek(0)

            # Encode the image to base64 string and decode to UTF-8
            image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            buf.close()

            # Update context with form, analysis results, and the plot image
            context.update({
                'image_base64': image_base64,
            })
        except EPWFile.DoesNotExist:
            context['message'] = 'EPW file not found. Please upload a file.'
    else:
        context['message'] = 'Please upload an EPW file to view weather statistics.'

    return render(request, 'firstapp/weatherstats.html', context)

def pv_tool(request):
    form = PVToolForm(request.POST or None)
    context = {'form': form, 'active_page': 'pv_tool'}

    chart = None  # Initialize chart variable
    
    if request.method == 'POST' and form.is_valid():
        
        epw_file_id = request.session.get('epw_file_id')
        epw_file_model = EPWFile.objects.get(id=epw_file_id)
        epw_file_path = epw_file_model.file.path
        epw_data = EPW(epw_file_path)

        width = form.cleaned_data['roof_width']
        length = form.cleaned_data['roof_length']
        pv_width = form.cleaned_data['pv_width']
        pv_height = form.cleaned_data['pv_height']
        height = 3.2
        h_seperation = 0.1
        v_seperation = 2.5

        # Create room and shade
        room = Room.from_box('test1', width, length, 3.2)  # Example height of 3.2
        v_offset = 0.05

        pv_array = []
        copy_d = pv_width+h_seperation
        rx = []

        axis_test = Vector3D(1,0,0)
        n_max = int(np.floor((width + h_seperation)/(pv_width + h_seperation))) #calculate max panels fitting horizontally

        for i in range(n_max):
            if i == 0:
                rx.append([
                [0, 0, height+v_offset],           # Bottom-left corner
                [pv_width, 0, height+v_offset],       # Bottom-right corner
                [pv_width, pv_height, height+v_offset],  # Top-right corner
                [0, pv_height, height+v_offset]       # Top-left corner
                ])
                
            else:
                rx.append([
            [copy_d*(i), 0, height+v_offset],           # Bottom-left corner
            [pv_width+(copy_d*(i)), 0, height+v_offset],       # Bottom-right corner
            [pv_width+(copy_d*(i)), pv_height, height+v_offset],  # Top-right corner
            [copy_d*(i), pv_height, height+v_offset]       # Top-left corner
            ])
       
            origin_start = Point3D(0,0,rx[i][0][2])
            x = Shade.from_vertices(str(i),vertices=rx[i])
            x.rotate(axis=axis_test,angle=20, origin=origin_start)
            
            pv_array.append(x)

        ry = []
        y_max = int(np.floor(length/v_seperation)) #calculate max panels fitting horizontally

        count = len(pv_array) + 1
        for k in range(y_max):
            for i in pv_array:
                p = i.vertices
                y = Shade.from_vertices(str(count), p)
                y.move(Vector3D(0,v_seperation*int(k),0))
                ry.append(y)
                count += 1

        for i in ry:
            pv_array.append(i)

        shades = []
        for pv in pv_array:
            shades.append(pv.duplicate())
            if math.degrees(Vector3D(0, 0, 1).angle(pv.normal)) - 90 > 1:
                msg = 'Shade "{}" is pointing downwards, which is atypical of photovoltaics.\n' \
                    'You will likely want to flip the geometry to have it point upwards to ' \
                    'the sky.'.format(pv.display_name)
                print(msg)
            
        # create the base PV properties
        display_name = 'Photovoltaic Array {}'.format(len(shades))
        print(display_name)
        pv_id = clean_ep_string(display_name)
        pv_props = PVProperties(pv_id)
        pv_props.display_name = pv_id
        for shade in shades:
            shade.properties.energy.pv_properties = pv_props


        print('------')
        #print(pv_array)
        model = Model('test1', rooms=[room], orphaned_shades=shades)
         # process the simulation parameters
        
        sim_par = SimulationParameter()
        sim_par.output.add_zone_energy_use()
        sim_par.output.add_hvac_energy_use()
        sim_par.output.add_electricity_generation()
       
        #sim_par = sim_par.duplicate()  # ensure input is not edited

        simfolder_path = os.path.join(settings.MEDIA_ROOT, 'simulations')
        clean_name = re.sub(r'[^.A-Za-z0-9_-]', '_', model.display_name)
        directory = os.path.join(simfolder_path, clean_name, 'openstudio')

        model = model.duplicate()
        model.properties.energy.remove_hvac_from_no_setpoints()
         # auto-assign stories if there are none since most OpenStudio measures need these
        if len(model.stories) == 0 and len(model.rooms) != 0:
            model.assign_stories_by_floor_height()

        nukedir(directory, True)
        preparedir(directory)
        sch_directory = os.path.join(directory, 'schedules')
        preparedir(sch_directory)

        # write the model parameter JSONs
        model_dict = model.to_dict(triangulate_sub_faces=True)
        model.properties.energy.add_autocal_properties_to_dict(model_dict)
        model_json = os.path.join(directory, '{}.hbjson'.format(clean_name))
        with open(model_json, 'wb') as fp:
            model_str = json.dumps(model_dict, ensure_ascii=False)
            fp.write(model_str.encode('utf-8'))


        # write the simulation parameter JSONs
        sim_par_dict = sim_par.to_dict()
        sim_par_json = os.path.join(directory, 'simulation_parameter.json')
        with open(sim_par_json, 'w') as fp:
            json.dump(sim_par_dict, fp)

        osw = to_openstudio_osw(osw_directory=directory, model_path=model_json, sim_par_json_path=sim_par_json, epw_file=epw_file_path)

        osm, idf = run_osw(osw)
        if idf is None:
            print('error null idf')
        sql = run_idf(idf,epw_file_path)[0]
        print(sql)

        production = generation_data_from_sql(sql)[0]
        print(production)
        monthly = production.total_monthly()
        print(monthly)

        modelVis = ModelVTK.from_hbjson(model_json)
        visualization_path = os.path.join(settings.MEDIA_ROOT, 'visualizations', 'room_pv')

        modelVis.to_html(folder=os.path.dirname(visualization_path), name=os.path.basename(visualization_path), show=False)

        visualization_relative_path = os.path.join('visualizations', 'room_pv.html')
        visualization_url = settings.MEDIA_URL + visualization_relative_path
        context['visualization_url'] = visualization_url

        #shade = Shade.from_dict
        monthly_generation = monthly.values  # Example kWh values
        
        # Set the Seaborn theme for nicer aesthetics
        sns.set_theme()

        # Plotting
        plt.figure(figsize=(10, 6))
        months = range(1, 13)
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        plt.bar(months, monthly_generation, color='SkyBlue')
        plt.xlabel('Month')
        plt.ylabel('Electricity Generated (kWh)')
        plt.title('Monthly PV Electricity Generation')
        plt.xticks(months, month_names)

        plt.tight_layout()

        # Convert plot to PNG image
        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close()
        
        # Encode PNG image to base64 string
        chart = base64.b64encode(buf.getvalue()).decode('utf-8')
        buf.close()

        context['chart'] = chart

    return render(request, 'firstapp/pvtool.html', context)

def energy_sim(request):
    context = {'active_page': 'energy_sim'}

    room = Room.from_box('test1', 5,5,3.2)
    room.wall_apertures_by_ratio(0.4)

    model = Model('test1', rooms=[room])
    hbjson = model.to_hbjson()

    modelVis = ModelVTK.from_hbjson(hbjson)
    visualization_path = os.path.join(settings.MEDIA_ROOT, 'visualizations', 'two-rooms')

    modelVis.to_html(folder=os.path.dirname(visualization_path), name=os.path.basename(visualization_path), show=False)

    visualization_relative_path = os.path.join('visualizations', 'two-rooms.html')
    visualization_url = settings.MEDIA_URL + visualization_relative_path
    context['visualization_url'] = visualization_url

    return render(request, 'firstapp/energysim.html', context)

def rainwater(request):
    context = {'active_page': 'rainwater'}
    
    if request.method == 'POST':
        form = CatchmentAreaForm(request.POST, request.FILES)
        if form.is_valid():
            # Extracted width, length, area from form
            width = form.cleaned_data.get('width')
            length = form.cleaned_data.get('length')
            area = form.cleaned_data.get('area')

            # Assuming 'epw_file' is the name of your FileField for EPW files
            epw_file = request.FILES.get('epw_file')
            if epw_file:
                # Process EPW file here to extract latitude and longitude
                latitude, longitude = extract_lat_long_from_epw(epw_file)  # Implement this function

                # Setup the Open-Meteo API client with cache and retry on error
                cache_session = requests_cache.CachedSession('.cache', expire_after=-1)
                retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
                openmeteo = openmeteo_requests.Client(session=retry_session)

                # API Call with extracted latitude and longitude
                url = "https://archive-api.open-meteo.com/v1/archive"
                params = {
                    "latitude": latitude,
                    "longitude": longitude,
                    "start_date": "2024-02-20",
                    "end_date": "2024-03-05",
                    "hourly": "rain"
                }
                responses = openmeteo.weather_api(url, params=params)

                # Assuming single location response for simplicity
                response = responses[0]
                hourly = response.Hourly()
                hourly_rain = hourly.Variables(0).ValuesAsNumpy()

                hourly_data = {"date": pd.date_range(
                    start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
                    end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
                    freq=pd.Timedelta(seconds=hourly.Interval()),
                    inclusive="left"
                )}
                hourly_data["rain"] = hourly_rain

                hourly_dataframe = pd.DataFrame(data=hourly_data)
                print(hourly_dataframe)  # Or process as needed

            calculated_area = area or (width * length)
            annual_rainfall = 1000  # This can be dynamic based on user input or other sources
            annual_storage = calculated_area * (annual_rainfall / 1000)
            
            context.update({
                'calculated_area': calculated_area,
                'annual_storage': annual_storage,
            })
    else:
        form = CatchmentAreaForm()
    
    context['form'] = form
    return render(request, 'firstapp/rainwater.html', context)






