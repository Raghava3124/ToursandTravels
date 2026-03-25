import http.server
import socketserver
import json
import csv
import os
import sys
from urllib.parse import urlparse, parse_qs

# Change working directory to the folder where this script is located
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    
os.chdir(script_dir)

PORT = 8000
CSV_FILE = os.path.join(script_dir, "Car_Bookings.csv")

class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == '/check_bookings':
            query = parse_qs(parsed_path.query)
            date_from = query.get('from', [''])[0]
            date_to = query.get('to', [''])[0]
            booked_cars = self.get_booked_cars(date_from, date_to)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"booked_cars": booked_cars}).encode())
        elif parsed_path.path == '/get_bill':
            query = parse_qs(parsed_path.query)
            s_no = query.get('sNo', [''])[0]
            bill_data = self.get_bill_by_sno(s_no)
            
            if bill_data:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "data": bill_data}).encode())
            else:
                self.send_response(404)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "not_found"}).encode())
        else:
            super().do_GET()

    def do_POST(self):
        # We only accept POST requests to /save_bill
        if self.path == '/save_bill':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                self.save_to_csv(data)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success"}).encode())
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        # Handle CORS preflight request
        self.send_response(200, "ok")
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def parse_csv_date(self, d):
        d = d.strip().strip("'").strip()
        parts = d.split('/')
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
        return d

    def check_overlap(self, from1, to1, from2, to2):
        return from1 <= to2 and from2 <= to1

    def get_booked_cars(self, date_from, date_to):
        if not os.path.isfile(CSV_FILE) or not date_from or not date_to:
            return {}
        booked = {}
        with open(CSV_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            headers = next(reader, None)
            if not headers:
                return {}
            
            from_idx, to_idx, car_idx, name_idx = -1, -1, -1, -1
            for i, h in enumerate(headers):
                if h == 'Booking From': from_idx = i
                elif h == 'Booking To': to_idx = i
                elif h == 'Booked Car Number': car_idx = i
                elif h == 'Name': name_idx = i
                elif h == 'Booking Date': from_idx = to_idx = i
                    
            if from_idx == -1 or to_idx == -1 or car_idx == -1:
                return {}
                
            for row in reader:
                if len(row) > max(from_idx, to_idx, car_idx):
                    csv_from = self.parse_csv_date(row[from_idx])
                    csv_to = self.parse_csv_date(row[to_idx])
                    car = row[car_idx]
                    
                    if not csv_from or not csv_to or not car: continue
                    
                    if self.check_overlap(date_from, date_to, csv_from, csv_to):
                        name = row[name_idx] if name_idx != -1 and len(row) > name_idx else "Unknown"
                        booked[car] = {
                            "name": name,
                            "from": csv_from,
                            "to": csv_to
                        }
        return booked

    def get_bill_by_sno(self, s_no):
        if not s_no or not os.path.isfile(CSV_FILE):
            return None
        s_no_str = str(s_no).strip()
        with open(CSV_FILE, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            headers = next(reader, None)
            if not headers:
                return None
            sno_idx = headers.index('S No') if 'S No' in headers else 0
            
            for row in reader:
                if len(row) > sno_idx and str(row[sno_idx]).strip() == s_no_str:
                    return {
                        'sNo': row[0] if len(row) > 0 else '',
                        'name': row[1] if len(row) > 1 else '',
                        'licenceNo': row[2] if len(row) > 2 else '',
                        'aadharNo': row[3] if len(row) > 3 else '',
                        'phoneNo': row[4] if len(row) > 4 else '',
                        'bookingFrom': self.parse_csv_date(row[5]) if len(row) > 5 else '',
                        'bookingTo': self.parse_csv_date(row[6]) if len(row) > 6 else '',
                        'bookedCar': row[7] if len(row) > 7 else '',
                        'startKm': row[8] if len(row) > 8 else '',
                        'endKm': row[9] if len(row) > 9 else '',
                        'totalKm': row[10] if len(row) > 10 else '',
                        'cngPoints': row[11] if len(row) > 11 else '',
                        'petrolPoints': row[12] if len(row) > 12 else '',
                        'amount': row[13] if len(row) > 13 else '',
                        'tollFee': row[14] if len(row) > 14 else '',
                        'lateFee': row[15] if len(row) > 15 else '',
                        'advance': row[16] if len(row) > 16 else '',
                        'balance': row[17] if len(row) > 17 else ''
                    }
        return None

    def save_to_csv(self, data):
        file_exists = os.path.isfile(CSV_FILE)
        headers = [
            'S No', 'Name',  'Licence Number', 
            'Aadhar Number', 'Phone Number', 'Booking From', 'Booking To', 'Booked Car Number', 
            'Start KM', 'End KM', 'Total KM', 'CNG Points', 
            'Petrol/Diesel Points', 'Amount', 'Toll Gate Fee', 
            'Late Fee', 'Advance Amount', 'Balance'
        ]
        
        def format_date(d):
            if not d: return ""
            parts = str(d).split('-')
            if len(parts) == 3:
                return f"'{parts[2]}/{parts[1]}/{parts[0]}"
            return str(d)
            
        new_row = [
            data.get('sNo', ''),
            data.get('name', ''),
            data.get('licenceNo', ''),
            data.get('aadharNo', ''),
            data.get('phoneNo', ''),
            format_date(data.get('bookingFrom', '')),
            format_date(data.get('bookingTo', '')),
            data.get('bookedCar', ''),
            data.get('startKm', ''),
            data.get('endKm', ''),
            data.get('totalKm', ''),
            data.get('cngPoints', ''),
            data.get('petrolPoints', ''),
            data.get('amount', ''),
            data.get('tollFee', ''),
            data.get('lateFee', ''),
            data.get('advance', ''),
            data.get('balance', '')
        ]

        try:
            if not file_exists:
                with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(headers)
                    writer.writerow(new_row)
                return

            rows = []
            updated = False
            sno_target = str(data.get('sNo', '')).strip()
            
            try:
                with open(CSV_FILE, mode='r', encoding='utf-8') as file:
                    reader = csv.reader(file)
                    existing_headers = next(reader, headers)
                    rows.append(existing_headers)
                    sno_idx = existing_headers.index('S No') if 'S No' in existing_headers else 0
                    
                    for row in reader:
                        if len(row) > sno_idx and str(row[sno_idx]).strip() == sno_target:
                            rows.append(new_row)
                            updated = True
                        else:
                            rows.append(row)
            except UnicodeDecodeError:
                rows = []
                with open(CSV_FILE, mode='r', encoding='cp1252', errors='replace') as file:
                    reader = csv.reader(file)
                    existing_headers = next(reader, headers)
                    rows.append(existing_headers)
                    sno_idx = existing_headers.index('S No') if 'S No' in existing_headers else 0
                    
                    for row in reader:
                        if len(row) > sno_idx and str(row[sno_idx]).strip() == sno_target:
                            rows.append(new_row)
                            updated = True
                        else:
                            rows.append(row)
                            
            if not updated:
                rows.append(new_row)
                
            with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerows(rows)
                
        except PermissionError:
            raise Exception("Cannot save because Car_Bookings.csv is currently open in another program (like Excel). Please close it and try again.")

print(f"Starting Local Driving School Server at http://localhost:{PORT}")
print("Please leave this black window open while using the software.")
print(f"Data will be saved automatically to {os.path.abspath(CSV_FILE)}")

with socketserver.TCPServer(("", PORT), RequestHandler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
