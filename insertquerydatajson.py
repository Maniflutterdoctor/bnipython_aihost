import mysql.connector
import requests

# MySQL connection config
db_config = {
    "host": "srv1836.hstgr.io",
    "user": "u258460312_bniuser",
    "password": "Sbva/tech1",  # Set your password
    "database": "u258460312_bni"  # Ensure this database exists
}

# URLs
DETAILS_URL = "https://bniapi.futureinfotechservices.in/BNI/bni_membersdeatilsgems.php"
SCORES_URL = "https://bniapi.futureinfotechservices.in/BNI/bniapiecomm.php"

# Connect to MySQL
conn = mysql.connector.connect(**db_config)
cursor = conn.cursor()

# Create member_details table
cursor.execute("""
CREATE TABLE IF NOT EXISTS member_details (
    id INT PRIMARY KEY,
    member_name VARCHAR(100),
    password VARCHAR(100),
    classification VARCHAR(100),
    company_name VARCHAR(100),
    phone VARCHAR(20),
    teamname VARCHAR(50),
    powerteam VARCHAR(100),
    user_type VARCHAR(50),
    activestatus VARCHAR(50)
);
""")

# Create member_scores table
cursor.execute("""
CREATE TABLE IF NOT EXISTS member_scores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    powerteam VARCHAR(100),
    total_score INT,
    referral_score INT,
    referral_maintain INT,
    referral_recom INT,
    tyftb_score INT,
    tyftb_maintain INT,
    tyftb_recom BIGINT,
    visitor_score INT,
    visitor_maintain INT,
    visitor_recom INT,
    testimonial_score INT,
    testimonial_maintain INT,
    testimonial_recom INT,
    training_score INT,
    training_maintain INT,
    training_recom INT,
    absent_score INT,
    absent_maintain INT,
    absent_recom INT,
    arrivingontime_score INT,
    arrivingontime_maintain INT,
    arrivingontime_recom INT
);
""")

# Fetch and insert member_details
response = requests.get(DETAILS_URL)
details_data = response.json().get("data", [])

for item in details_data:
    cursor.execute("""
        REPLACE INTO member_details 
        (id, member_name, password, classification, company_name, phone, teamname, powerteam, user_type, activestatus)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        item["id"],
        item["member_name"],
        item["password"],
        item["classification"],
        item["company_name"],
        item["phone"],
        item["teamname"],
        item["powerteam"],
        item["user_type"],
        item["activestatus"]
    ))

# Fetch and insert member_scores
response = requests.get(SCORES_URL)
score_data = response.json().get("data", [])

for item in score_data:
    cursor.execute("""
        INSERT INTO member_scores (
            name, powerteam, total_score,
            referral_score, referral_maintain, referral_recom,
            tyftb_score, tyftb_maintain, tyftb_recom,
            visitor_score, visitor_maintain, visitor_recom,
            testimonial_score, testimonial_maintain, testimonial_recom,
            training_score, training_maintain, training_recom,
            absent_score, absent_maintain, absent_recom,
            arrivingontime_score, arrivingontime_maintain, arrivingontime_recom
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        item["NAME"],
        item["powerteam"],
        int(item["Total_Score"]),
        item["Referral_Score"],
        item["Referral_maintain"],
        item["Referral_Recom"],
        item["TYFTB_Score"],
        item["TYFTB_maintain"],
        item["TYFTB_Recom"],
        item["Visitor_Score"],
        item["Visitor_maintain"],
        item["Visitor_Recom"],
        item["Testimonial_Score"],
        item["Testimonial_maintain"],
        item["Testimonial_Recom"],
        item["Training_Score"],
        item["Training_maintain"],
        item["Training_Recom"],
        item["Absent_Score"],
        item["Absent_maintain"],
        item["Absent_Recom"],
        item["Arrivingontime_Score"],
        item["Arrivingontime_maintain"],
        item["Arrivingontime_Recom"]
    ))

# Commit and close
conn.commit()
cursor.close()
conn.close()

print("Data inserted successfully!")
