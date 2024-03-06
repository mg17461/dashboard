from django.shortcuts import render, redirect
from .forms import EPWUploadForm
from .models import EPWFile
# Import Ladybug Tools for analysis
from ladybug.epw import EPW
from honeybee.room import Room
from honeybee.model import Model
from honeybee_vtk.model import Model as ModelVTK
import os
from django.conf import settings  # Add this import at the top of your views.py

import numpy as np
import matplotlib
import seaborn as sns

import base64
import matplotlib.pyplot as plt
from io import BytesIO

def benchmarks(request):
    context = {'active_page': 'benchmarks'}
    return render(request, 'firstapp/benchmarks.html', context)

def weather_stats(request):
    context = {'active_page': 'weather_stats', 'form': EPWUploadForm()}  # Initialize context with form and active_page
    if request.method == 'POST':
        form = EPWUploadForm(request.POST, request.FILES)
        if form.is_valid():
            epw_instance = form.save()
            # Assuming you're saving the file in MEDIA_ROOT/epw_files/
            epw_file_path = epw_instance.file.path
            
            # Assuming 'grouped' is your OrderedDict with monthly temperature data
            monthly_averages = []
            monthly_mins = []
            monthly_maxs = []

            # Perform analysis with Ladybug Tools
            epw_data = EPW(epw_file_path)

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
                'form': form,
                'image_base64': image_base64,
            })


    return render(request, 'firstapp/weatherstats.html', context)

def pv_tool(request):
    context = {'active_page': 'pv_tool'}
    return render(request, 'firstapp/pvtool.html', context)

def energy_sim(request):
    context = {'active_page': 'energy_sim'}

    room = Room.from_box('test1', 5,5,3.2)
    room.wall_apertures_by_ratio(0.4)

    model = Model('test1', rooms=[room])
    hbjson = model.to_hbjson()

    modelVis = ModelVTK.from_hbjson(hbjson)
    visualization_path = os.path.join(settings.MEDIA_ROOT, 'visualizations', 'two-rooms.html')

    modelVis.to_html(folder=os.path.dirname(visualization_path), name=os.path.basename(visualization_path), show=False)

    visualization_relative_path = os.path.join('visualizations', 'two-rooms.html')
    visualization_url = settings.MEDIA_URL + visualization_relative_path
    context['visualization_url'] = visualization_url

    return render(request, 'firstapp/energysim.html', context)



