
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize Supabase client
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

@app.route("/")
def home():
    return send_file("index.html")

@app.route('/api/register', methods=['POST'])
def register_patient():
    """Register a new patient and allocate a bed"""
    try:
        data = request.json
        
        # Extract patient data from request
        patient_id = data.get('patientId')
        name = data.get('patientName')
        phone = data.get('patientPhone')
        age = data.get('patientAge')
        address = data.get('patientAddress')
        condition = data.get('patientCondition')
        ward_type = data.get('ward')
        
        # Validate required fields
        if not all([patient_id, name, phone, age, address, condition, ward_type]):
            return jsonify({"success": False, "message": "All fields are required"}), 400
            
        # Step 1: Insert patient data
        patient_result = supabase.table('patients').insert({
            "patient_id": patient_id,
            "name": name,
            "phone": phone,
            "age": int(age),
            "address": address,
            "condition_notes": condition
        }).execute()
        
        # Step 2: Find an available bed in the requested ward
        bed_result = supabase.table('beds') \
            .select('bed_id, bed_number') \
            .eq('status', 'vacant') \
            .eq('ward_id', supabase.table('wards').select('ward_id').eq('ward_name', ward_type).limit(1)) \
            .limit(1) \
            .execute()
            
        # Check if bed is available
        if not bed_result.data:
            return jsonify({
                "success": False, 
                "message": f"No beds available in {ward_type} ward"
            }), 409
            
        bed_id = bed_result.data[0]['bed_id']
        bed_number = bed_result.data[0]['bed_number']
        
        # Step 3: Update bed status to occupied
        supabase.table('beds') \
            .update({"status": "occupied"}) \
            .eq('bed_id', bed_id) \
            .execute()
            
        # Step 4: Create admission record
        admission_result = supabase.table('admissions').insert({
            "patient_id": patient_id,
            "bed_id": bed_id,
            "status": "active"
        }).execute()
        
        return jsonify({
            "success": True,
            "message": f"Patient registered and allocated to bed {bed_number} in {ward_type} ward",
            "bed_number": bed_number,
            "ward": ward_type
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard_data():
    """Get data for the dashboard"""
    try:
        # Get bed statistics
        bed_stats = supabase.rpc('get_bed_stats').execute()
        
        # Get recent admissions
        recent_admissions = supabase.table('admissions') \
            .select('admission_id, admission_date, patients(name), beds(bed_number, wards(ward_name))') \
            .eq('status', 'active') \
            .order('admission_date', desc=True) \
            .limit(10) \
            .execute()
            
        # Get ward occupancy
        ward_occupancy = supabase.rpc('get_ward_occupancy').execute()
        
        return jsonify({
            "success": True,
            "bed_stats": bed_stats.data,
            "recent_admissions": recent_admissions.data,
            "ward_occupancy": ward_occupancy.data
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/discharge', methods=['POST'])
def discharge_patient():
    """Discharge a patient"""
    try:
        data = request.json
        admission_id = data.get('admissionId')
        
        if not admission_id:
            return jsonify({"success": False, "message": "Admission ID is required"}), 400
            
        # Get bed_id from admission record
        admission = supabase.table('admissions') \
            .select('bed_id') \
            .eq('admission_id', admission_id) \
            .single() \
            .execute()
            
        if not admission.data:
            return jsonify({"success": False, "message": "Admission not found"}), 404
            
        bed_id = admission.data['bed_id']
        
        # Update admission status and discharge date
        supabase.table('admissions') \
            .update({
                "status": "discharged",
                "discharge_date": datetime.now().isoformat()
            }) \
            .eq('admission_id', admission_id) \
            .execute()
            
        # Mark bed as vacant
        supabase.table('beds') \
            .update({"status": "vacant"}) \
            .eq('bed_id', bed_id) \
            .execute()
            
        return jsonify({
            "success": True,
            "message": "Patient discharged successfully"
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# Add these stored procedures to your Supabase database
"""
-- Function to get bed statistics
CREATE OR REPLACE FUNCTION get_bed_stats()
RETURNS TABLE (
    total_beds INTEGER,
    occupied_beds INTEGER,
    vacant_beds INTEGER,
    maintenance_beds INTEGER
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::INTEGER AS total_beds,
        COUNT(*) FILTER (WHERE status = 'occupied')::INTEGER AS occupied_beds,
        COUNT(*) FILTER (WHERE status = 'vacant')::INTEGER AS vacant_beds,
        COUNT(*) FILTER (WHERE status = 'maintenance')::INTEGER AS maintenance_beds
    FROM beds;
END;
$$;

-- Function to get ward occupancy
CREATE OR REPLACE FUNCTION get_ward_occupancy()
RETURNS TABLE (
    ward_name VARCHAR,
    total INTEGER,
    occupied INTEGER,
    vacant INTEGER,
    occupancy_rate NUMERIC
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        w.ward_name,
        COUNT(b.bed_id)::INTEGER AS total,
        COUNT(b.bed_id) FILTER (WHERE b.status = 'occupied')::INTEGER AS occupied,
        COUNT(b.bed_id) FILTER (WHERE b.status = 'vacant')::INTEGER AS vacant,
        ROUND((COUNT(b.bed_id) FILTER (WHERE b.status = 'occupied')::NUMERIC / 
              NULLIF(COUNT(b.bed_id), 0)::NUMERIC * 100), 2) AS occupancy_rate
    FROM wards w
    JOIN beds b ON w.ward_id = b.ward_id
    GROUP BY w.ward_name;
END;
$$;
"""

if __name__ == '__main__':
    app.run(debug=True)
