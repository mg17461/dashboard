from django.shortcuts import render, redirect
from .forms import EPWUploadForm
from .forms import CatchmentAreaForm
from .forms import PVToolForm
from .models import EPWFile
# Import Ladybug Tools for analysis
from ladybug.epw import EPW
from honeybee.room import Room
from honeybee.model import Model
from honeybee.shade import Shade
from honeybee_energy.generator.pv import PVProperties
#from honeybee_energy.run import RunEnergySimulation
from honeybee_vtk.model import Model as ModelVTK
import os
from django.conf import settings  # Add this import at the top of your views.py
import openmeteo_requests
import requests_cache
import pandas as pd
from retry_requests import retry

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
        width = form.cleaned_data['roof_width']
        length = form.cleaned_data['roof_length']
        height = 3.2
        # Dummy data for monthly PV electricity generation

        # Create room and shade
        room = Room.from_box('test1', width, length, 3.2)  # Example height of 3.2
        offset = 0.05
        roof_vertices = [
        [0, 0, height+offset],           # Bottom-left corner
        [width, 0, height+offset],       # Bottom-right corner
        [width, length, height+offset],  # Top-right corner
        [0, length, height+offset]       # Top-left corner
        ]

        # Convert tuples to Point3D objects
        pv_shade = Shade.from_vertices('shade1',vertices=roof_vertices)

        model = Model('test1', rooms=[room], orphaned_shades=[pv_shade])
        hbjson = model.to_hbjson()

        modelVis = ModelVTK.from_hbjson(hbjson)
        visualization_path = os.path.join(settings.MEDIA_ROOT, 'visualizations', 'room_pv')

        modelVis.to_html(folder=os.path.dirname(visualization_path), name=os.path.basename(visualization_path), show=False)

        visualization_relative_path = os.path.join('visualizations', 'room_pv.html')
        visualization_url = settings.MEDIA_URL + visualization_relative_path
        context['visualization_url'] = visualization_url

        #shade = Shade.from_dict
        monthly_generation = [120, 130, 150, 170, 160, 180, 200, 190, 210, 200, 220, 210]  # Example kWh values
        
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






