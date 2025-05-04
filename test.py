# test_connection.py
from dotenv import load_dotenv
import os
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# Test connection
try:
    response = supabase.table('wards').select('*').execute()
    print("Connection successful!")
    print("Wards in database:", len(response.data))
    for ward in response.data:
        print(f"- {ward['ward_name']}: {ward['total_beds']} beds")
except Exception as e:
    print("Connection failed:", str(e))
