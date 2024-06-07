from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
import json
import datetime
from reportlab.lib.pagesizes import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
import os
import time
import zipfile
import io

app = Flask(__name__)

# Define tabloid size manually
tabloid = (11 * inch, 17 * inch)

# Load existing data or initialize an empty structure
try:
    with open("travelers.json", "r") as f:
        data = json.load(f)
except FileNotFoundError:
    data = {"travelers": [], "last_serial_number": 0}

# Ensure 'last_serial_number' exists in the data dictionary
if 'last_serial_number' not in data:
    data['last_serial_number'] = 0

# Function to save data to JSON file
def save_data():
    with open("travelers.json", "w") as f:
        json.dump(data, f, indent=4)

# Helper function for word wrapping
def wrap_text(text, width, canvas, font_name, font_size, max_lines=3):
    canvas.setFont(font_name, font_size)
    lines = simpleSplit(text, font_name, font_size, width)
    return lines[:max_lines]  # Limit to max_lines lines

# Function to generate PDF
def generate_pdf(traveler):
    if not os.path.exists('static'):
        os.makedirs('static')

    # Format the filename as date_serialnumber
    date_str = datetime.datetime.strptime(traveler['date'], '%Y-%m-%d').strftime('%Y%m%d')
    pdf_filename = f"{date_str}_{traveler['serial_number']}.pdf"
    pdf_path = os.path.join('static', pdf_filename)
    
    # Remove the existing PDF file if it exists to avoid permission issues
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    c = canvas.Canvas(pdf_path, pagesize=tabloid)

    # Define starting coordinates and margins
    x_margin = 10
    y_start = 1200
    line_height = 30
    description_width = 280  
    part_number_width = 100 
    location_width = 200

    y_position = y_start

    def draw_header():
        nonlocal y_position
        c.setFont("Helvetica-Bold", 28)
        c.drawString(x_margin, y_position, "Traveler Information")
        y_position -= line_height

        c.setFont("Helvetica-Bold", 22)
        c.drawString(x_margin, y_position, f"Serial Number: {traveler['serial_number']}")
        c.drawString(x_margin + 450, y_position, f"Pallet Number: {traveler['pallet_number']}")
        y_position -= line_height

        c.setFont("Helvetica", 20)
        c.drawString(x_margin, y_position, f"Name: {traveler['name']}")
        c.drawString(x_margin + 450, y_position, f"Pallet Type: {traveler['pallet_type']}")
        y_position -= line_height
        c.drawString(x_margin, y_position, f"Date: {traveler['date']}")
        c.drawString(x_margin + 450, y_position, f"Pallet Contents: {traveler['pallet_contents']}")
        y_position -= line_height * 2

    def draw_column_headings():
        nonlocal y_position
        c.setFont("Helvetica-Bold", 18)
        c.drawString(x_margin, y_position, "Part Number")
        c.drawString(x_margin + 140, y_position, "Description")
        c.drawString(x_margin + 430, y_position, "Qty Boxes")
        c.drawString(x_margin + 540, y_position, "Total Qty")
        c.drawString(x_margin + 650, y_position, "Locations")
        y_position -= line_height / 2
        c.line(0, y_position, x_margin + 1550, y_position)
        y_position -= line_height

    def draw_part_details():
        nonlocal y_position
        c.setFont("Helvetica", 16)
        for part in traveler['parts']:
            if y_position < 100:
                c.showPage()
                y_position = y_start
                draw_header()
                draw_column_headings()

            part_number_lines = wrap_text(part['part_number'], part_number_width, c, "Helvetica", 16, max_lines=2)
            description_lines = wrap_text(part['description'], description_width, c, "Helvetica", 16)
            location_lines = [loc.strip() for loc in part['from_locations']]  # Trim spaces around locations

            line_y_position = y_position
            for line in part_number_lines:
                c.drawString(x_margin, line_y_position, line)
                line_y_position -= line_height / 2

            line_y_position = y_position
            for line in description_lines:
                c.drawString(x_margin + 140, line_y_position, line)
                line_y_position -= line_height / 2
                
            c.drawString(x_margin + 430, y_position, str(part['qty_boxes']))
            c.drawString(x_margin + 540, y_position, str(part['total_qty']))

            line_y_position = y_position
            for location in location_lines:
                c.drawString(x_margin + 650, line_y_position, location)
                line_y_position -= line_height / 2

            y_position -= max(line_height, (len(description_lines) * (line_height / 2)), (len(location_lines) * (line_height / 2)))
            c.line(0, y_position - 5, x_margin + 1550, y_position - 5)
            y_position -= line_height

    draw_header()
    draw_column_headings()
    draw_part_details()
    c.save()

    return pdf_path

@app.route('/')
def index():
    today = datetime.date.today().strftime('%Y-%m-%d')
    return render_template('index.html', today=today)

@app.route('/create_traveler', methods=['POST'])
def create_traveler():
    name = request.form['name']
    pallet_number = request.form['pallet_number']
    pallet_type = request.form['pallet_type']
    pallet_contents = request.form['pallet_contents']
    date = request.form.get('date', str(datetime.date.today()))

    parts = []
    part_numbers = request.form.getlist('part_number')
    descriptions = request.form.getlist('description')
    qty_boxes_list = request.form.getlist('qty_boxes')
    total_qty_list = request.form.getlist('total_qty')
    from_locations_list = request.form.getlist('from_locations')

    print("Part Numbers:", part_numbers)  # Debug statement
    print("Descriptions:", descriptions)  # Debug statement
    print("Qty Boxes List:", qty_boxes_list)  # Debug statement
    print("Total Qty List:", total_qty_list)  # Debug statement
    print("From Locations List:", from_locations_list)  # Debug statement

    for i in range(len(part_numbers)):
        part = {
            "part_number": part_numbers[i],
            "description": descriptions[i],
            "qty_boxes": int(qty_boxes_list[i]),
            "total_qty": int(total_qty_list[i]),
            "from_locations": from_locations_list[i].split(',')
        }
        parts.append(part)

    serial_number = data["last_serial_number"] + 1
    data["last_serial_number"] = serial_number

    traveler = {
        "serial_number": serial_number,
        "name": name,
        "date": date,
        "pallet_number": pallet_number,
        "pallet_type": pallet_type,
        "pallet_contents": pallet_contents,
        "parts": parts,
        "versions": []
    }
    data["travelers"].append(traveler)
    save_data()
    pdf_path = generate_pdf(traveler)
    return send_file(pdf_path, as_attachment=True)


@app.route('/download_all')
def download_all():
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zf:
        for traveler in data['travelers']:
            pdf_path = generate_pdf(traveler)
            zf.write(pdf_path, os.path.basename(pdf_path))
    zip_buffer.seek(0)
    return send_file(zip_buffer, as_attachment=True, download_name='all_travelers.zip', mimetype='application/zip')

@app.route('/search')
def search():
    return render_template('search.html')

@app.route('/search_results', methods=['POST'])
def search_results():
    search_type = request.form['search_type']
    search_query = request.form['search_query']

    if search_type == 'serial_number':
        travelers = [traveler for traveler in data['travelers'] if str(traveler['serial_number']) == search_query]
    elif search_type == 'part_number':
        travelers = [traveler for traveler in data['travelers'] if any(part['part_number'] == search_query for part in traveler['parts'])]
    else:
        travelers = []

    return render_template('search_results.html', travelers=travelers)

@app.route('/view_traveler/<serial_number>')
def view_traveler(serial_number):
    traveler = next((traveler for traveler in data['travelers'] if str(traveler['serial_number']) == serial_number), None)
    if traveler:
        return render_template('view_traveler.html', traveler=traveler)
    else:
        return "Traveler not found", 404

@app.route('/edit_traveler/<serial_number>', methods=['GET', 'POST'])
def edit_traveler(serial_number):
    traveler = next((traveler for traveler in data['travelers'] if str(traveler['serial_number']) == serial_number), None)
    if not traveler:
        return "Traveler not found", 404

    if request.method == 'POST':
        traveler['name'] = request.form['name']
        traveler['pallet_number'] = request.form['pallet_number']
        traveler['pallet_type'] = request.form['pallet_type']
        traveler['pallet_contents'] = request.form['pallet_contents']
        traveler['date'] = request.form.get('date', traveler['date'])

        parts = []
        part_numbers = request.form.getlist('part_number')
        descriptions = request.form.getlist('description')
        qty_boxes_list = request.form.getlist('qty_boxes')
        total_qty_list = request.form.getlist('total_qty')
        from_locations_list = request.form.getlist('from_locations')

        for i in range(len(part_numbers)):
            if request.form.get(f'part_deleted_{i + 1}') == "false":  # Check if part is marked as deleted
                part = {
                    "part_number": part_numbers[i],
                    "description": descriptions[i],
                    "qty_boxes": int(qty_boxes_list[i]),
                    "total_qty": int(total_qty_list[i]),
                    "from_locations": from_locations_list[i].split(',')
                }
                parts.append(part)

        traveler['parts'] = parts
        save_data()
        generate_pdf(traveler)
        return redirect(url_for('view_traveler', serial_number=serial_number))

    return render_template('edit_traveler.html', traveler=traveler)

@app.route('/reprint_traveler/<serial_number>')
def reprint_traveler(serial_number):
    traveler = next((traveler for traveler in data['travelers'] if str(traveler['serial_number']) == serial_number), None)
    if traveler:
        generate_pdf(traveler)
        return redirect(url_for('view_traveler', serial_number=serial_number))
    else:
        return "Traveler not found", 404

if __name__ == '__main__':
    app.run(debug=True)
