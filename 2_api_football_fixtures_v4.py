import network
import urequests
import time
import os
import machine
import sdcard
from machine import Pin, SPI
from picographics import PicoGraphics, DISPLAY_INKY_FRAME_7
from pngdec import PNG
import uasyncio as asyncio
import gc
import battery_smol

# Import Wi-Fi credentials and API key
from WIFI_CONFIG import SSID, PASSWORD
from API_KEY import API_KEY

# Initialize the display for Inky Frame 7.3"
display = PicoGraphics(display=DISPLAY_INKY_FRAME_7)
png = PNG(display)  # Initialize the PNG decoder

# Set colors
WHITE = display.create_pen(255, 255, 255)
BLACK = display.create_pen(0, 0, 0)
RED = display.create_pen(180, 0, 0)
GRAY = display.create_pen(128, 128, 128)
GREEN = display.create_pen(0, 255, 0)
BLUE = display.create_pen(0, 0, 255)
YELLOW = display.create_pen(255, 255, 0)  # For yellow cards

# Set up the SD card
sd_spi = SPI(0, sck=Pin(18, Pin.OUT), mosi=Pin(19, Pin.OUT), miso=Pin(16, Pin.OUT))
sd = sdcard.SDCard(sd_spi, machine.Pin(22))
os.mount(sd, "/sd")

# Comment out the mockup data source
# import json
# with open('/sd/fixtures.json', 'r') as file:
#     fixtures_data = json.load(file)

# Clear the display with a white background before drawing anything
display.set_pen(WHITE)
display.clear()

# Create GUI elements
battery_smol.display_battery(display)  # Call the function to display the battery information

# Set the font to bitmap8
display.set_font("bitmap8")

# Define league ID and season globally
#LEAGUE_ID = 39  # Premier League ID
LEAGUE_ID = 129  # Premier League ID
SEASON = 2024  # Current season

# Function to get the date and day name for the next `n` days in DD-MM-YYYY format
def get_date_and_day(n):
    t = time.localtime(time.time() + n * 86400)
    date = f"{t[2]:02d}-{t[1]:02d}-{t[0]}"  # Format as DD-MM-YYYY
    day_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][t[6]]
    return date, day_name

# Function to determine if a given date is during BST (last Sunday in March to last Sunday in October)
def is_bst(date_tuple):
    year = date_tuple[0]
    last_march_sunday = max(day for day in range(31, 24, -1) if time.localtime(time.mktime((year, 3, day, 0, 0, 0, 0, 0)))[6] == 6)
    last_october_sunday = max(day for day in range(31, 24, -1) if time.localtime(time.mktime((year, 10, day, 0, 0, 0, 0, 0)))[6] == 6)
    start_bst = (year, 3, last_march_sunday, 1, 0, 0, 0, 0)  # BST starts at 1 AM on the last Sunday in March
    end_bst = (year, 10, last_october_sunday, 1, 0, 0, 0, 0)  # BST ends at 1 AM on the last Sunday in October
    start_bst_ts = time.mktime(start_bst)
    end_bst_ts = time.mktime(end_bst)
    current_ts = time.mktime(date_tuple)
    return start_bst_ts <= current_ts < end_bst_ts

# Function to convert UTC time string (HH:MM) to local time (considering BST/GMT)
def convert_utc_to_local(utc_time_str):
    hour_utc, minute = map(int, utc_time_str.split(":"))
    local_time = time.localtime()
    time_offset = 1 if is_bst(local_time) else 0  # BST (UTC+1) if DST is active, otherwise GMT (UTC+0)
    hour_local = (hour_utc + time_offset) % 24
    return f"{hour_local:02d}:{minute:02d}"

# Async function to connect to Wi-Fi
async def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    while not wlan.isconnected():
        await asyncio.sleep(1)
    print("Connected to Wi-Fi")

# Async function to fetch the current league standings
async def fetch_standings():
    url = f'https://v3.football.api-sports.io/standings?league={LEAGUE_ID}&season={SEASON}'
    headers = {'x-apisports-key': API_KEY}
    response = urequests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        standings = data['response'][0]['league']['standings'][0]
        positions = {team['team']['id']: team['rank'] for team in standings}
        return positions
    else:
        print("Failed to fetch standings:", response.status_code)
        return {}

# Async function to fetch fixture events like goals and cards
async def fetch_fixture_events(fixture_id):
    gc.collect()  # Collect garbage to free up memory before the request
    url = f'https://v3.football.api-sports.io/fixtures/events?fixture={fixture_id}'
    headers = {'x-apisports-key': API_KEY}
    response = urequests.get(url, headers=headers)
    details = []
    if response.status_code == 200:
        events = response.json()['response']
        for event in events:
            if event['type'] == 'Goal':
                scorer = event['player']['name']
                details.append(f"{scorer} ({event['time']['elapsed']}')")
            elif event['type'] == 'Card':
                card_type = 'Yellow' if event['detail'] == 'Yellow Card' else 'Red'
                card_color = YELLOW if card_type == 'Yellow' else RED
                display.set_pen(card_color)
                details.append(f"{event['player']['name']} {card_type} ({event['time']['elapsed']}')")
    else:
        print("Failed to fetch events:", response.status_code)
    response.close()
    return details

# Function to wrap text based on a maximum character count per line
def wrap_text(text, max_length):
    words = text.split(" ")
    lines = []
    current_line = ""

    for word in words:
        if len(current_line) + len(word) + 1 <= max_length:
            if current_line:
                current_line += " "
            current_line += word
        else:
            lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines

def load_and_display_crest(team_id, x, y):
    crest_filename = f"/sd/{team_id}.png"
    
    try:
        os.stat(crest_filename)  # Check if the file exists
        png.open(crest_filename)
        png.decode(x, y, png.PNG_TO_DISPLAY)
    except OSError:
        # If the file does not exist, draw a black square
        display.set_pen(BLACK)
        display.rectangle(x, y, 20, 20)

async def fetch_and_display_fixtures(positions):
    y_position = 10  # Starting y-position for the first day's fixtures
    base_line_height = 35  # Base space between rows to fit more fixtures

    for n in range(3):  # Loop over today, tomorrow, and the day after
        date, day_name = get_date_and_day(n)
        print(date, day_name)

        # Display the date and day name
        display.set_pen(BLUE)
        display.text(f"{day_name}, {date}", 10, y_position, scale=1)
        y_position += 10  # Move down slightly after the day and date

        # Draw a full-width horizontal line just below the day and date
        display.line(0, y_position, display.get_bounds()[0], y_position)
        y_position += 10  # Adjust spacing after the line

        # Fetch the day's fixtures
        url = f'https://v3.football.api-sports.io/fixtures?league={LEAGUE_ID}&date={date[6:]}-{date[3:5]}-{date[0:2]}&season={SEASON}'
        headers = {'x-apisports-key': API_KEY}
        response = urequests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            fixtures = data['response']

            if not fixtures:
                display.set_pen(RED)
                display.text("No fixtures found.", 10, y_position, scale=2)
                y_position += base_line_height
            else:
                y_position += 10  # Space between the day/date and the first match

                for fixture in fixtures:
                    fixture_id = fixture['fixture']['id']
                    fixture_time_utc = fixture['fixture']['date'][11:16]  # Time of the fixture (HH:MM) in UTC

                    # Convert UTC time to local time
                    fixture_time_local = convert_utc_to_local(fixture_time_utc)

                    home_team = fixture['teams']['home']['name']
                    away_team = fixture['teams']['away']['name']
                    home_team_id = fixture['teams']['home']['id']
                    away_team_id = fixture['teams']['away']['id']
                    home_score = fixture['goals']['home']
                    away_score = fixture['goals']['away']
                    status = fixture['fixture']['status']['short']

                    # Determine what to display: time or score
                    if status in ['NS', 'TBD']:  # 'NS' = Not Started, 'TBD' = To Be Decided
                        score_display = fixture_time_local
                        pen_color = RED  # Use red for match times
                    else:
                        score_display = f"{home_score} - {away_score}"
                        pen_color = BLACK  # Use black for scores

                    # Adjust positions
                    score_x = 240  # Position for the score display at 240px
                    score_width = display.measure_text(score_display, scale=2)

                    # Calculate the position of the home team name and crest
                    home_crest_x = score_x - 25  # Position crest to the left of the score
                    home_team_name_x = home_crest_x - display.measure_text(home_team[:17], scale=2) - 5  # 5px gap between crest and name

                    # Calculate the superscript position for the home team
                    if home_team_id in positions:
                        league_position = str(positions[home_team_id])
                        superscript_x = home_team_name_x - display.measure_text(league_position, scale=1) - 3
                        display.set_pen(RED)
                        display.text(league_position, superscript_x, y_position - 3, scale=1)  # Position superscript to the left

                    # Display the home team name
                    display.set_pen(BLACK)
                    display.text(f"{home_team[:17]}", home_team_name_x, y_position + 5, scale=2)  # Align name with crest

                    # Display the home team crest
                    load_and_display_crest(home_team_id, home_crest_x, y_position + 3)  # Slight vertical adjustment

                    # Display the time/score
                    display.set_pen(pen_color)  # Set pen color based on whether it's a time or score
                    display.text(score_display, score_x, y_position + 5, scale=2)  # Align time/score

                    # Calculate the position of the away team crest and name
                    away_crest_x = score_x + score_width + 5  # Shift slightly right of score
                    away_team_name_x = away_crest_x + 20 + 5  # 20px for crest, 5px gap from crest

                    # Display the away team crest
                    load_and_display_crest(away_team_id, away_crest_x, y_position + 3)

                    # Display the away team name
                    display.set_pen(BLACK)
                    display.text(f"{away_team[:17]}", away_team_name_x, y_position + 5, scale=2)

                    # Display league position as a smaller superscript in red for away team
                    if away_team_id in positions:
                        league_position = str(positions[away_team_id])
                        display.set_pen(RED)
                        superscript_x = away_team_name_x + display.measure_text(away_team[:17], scale=2) + 5
                        display.text(league_position, superscript_x, y_position - 3, scale=1)

                    # Fetch and display match details like goal scorers and cards
                    details = await fetch_fixture_events(fixture_id)
                    detail_x_offset = 515  # X-position for details
                    wrapped_lines = wrap_text("; ".join(details), 60)

                    # Calculate vertical offset for centering the wrapped lines
                    total_lines = len(wrapped_lines)
                    vertical_offset = ((total_lines - 1) * 10) // 2 - 8

                    # Display each wrapped line
                    for i, line in enumerate(wrapped_lines):
                        display.set_pen(BLACK)
                        display.text(line, detail_x_offset, y_position - vertical_offset + (i * 10), scale=1)

                    # Adjust y_position for the next fixture, considering the number of wrapped lines
                    y_position += base_line_height + (total_lines - 1) * 5  # Adjusted for details

                y_position += 5  # Extra space after finishing a day's fixtures

        else:
            print("Failed to fetch data:", response.status_code)

        response.close()

    #display.update()





# Main function to run all tasks
async def main():        
    await connect_wifi()  # Connect to Wi-Fi
    positions = await fetch_standings()  # Fetch the league standings
    await fetch_and_display_fixtures(positions)  # Fetch and display fixtures with league positions
    
    # Update the display after drawing everything
    display.update()
    
    # Final garbage collection
    gc.collect()

# Run the main function
asyncio.run(main())

