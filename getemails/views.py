from django.shortcuts import render

# Create your views here.
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.core.files.storage import FileSystemStorage
from io import BytesIO
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from concurrent.futures import ThreadPoolExecutor
import os
import logging

# Setting up logger
logger = logging.getLogger(__name__)

def find_url_column(columns):
    keywords = ['website', 'url', 'websites', 'urls']
    for col in columns:
        if any(keyword in col.lower() for keyword in keywords):
            return col
    return None

def extract_emails_from_url(url):
    if pd.isna(url) or not isinstance(url, str):
        return ""
    if not url.startswith(('http://', 'https://')):
        url = f"http://{url}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        text = ' '.join(soup.stripped_strings)
        raw_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        valid_emails = [email for email in raw_emails if not email[0].isdigit()]
        return ', '.join(set(valid_emails)) if valid_emails else "No email ID found"
    except requests.exceptions.RequestException:
        return "URL not working"
    except Exception as e:
        return f"Error: {str(e)}"

def get_optimal_workers(file_size):
    if file_size <= 100:
        return 5
    elif file_size <= 300:
        return 10
    else:
        return 20

def process_urls_in_parallel(df, url_column, num_workers):
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        return list(executor.map(extract_emails_from_url, df[url_column]))

def upload_file(request):
    return render(request, 'upload.html')

def process_file(request):
    if request.method == 'POST' and request.FILES['file']:
        file = request.FILES['file']
        if not file.name.endswith('.xlsx'):
            return JsonResponse({"error": "Invalid file type. Please upload an Excel file."}, status=400)
        try:
            df = pd.read_excel(file)
            url_column = find_url_column(df.columns)
            if not url_column:
                return JsonResponse({"error": "No column found that likely contains URLs."}, status=400)

            num_workers = get_optimal_workers(len(df))
            df['Emails'] = process_urls_in_parallel(df, url_column, num_workers)

            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            output.seek(0)

            processed_filename = f"processed_{file.name}"
            response = HttpResponse(output, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename={processed_filename}'
            return response
        except Exception as e:
            return JsonResponse({"error": f"An error occurred: {str(e)}"}, status=500)
    return JsonResponse({"error": "No file uploaded."}, status=400)
