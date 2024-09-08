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

# Clear the display with a white background before drawing anything
display.set_pen(WHITE)
display.clear()

# Create GUI elements
battery_smol.display_battery(display)  # Call the function to display the battery information

# Set the font to bitmap8
display.set_font("bitmap8")

# Define league ID globally (Premier League ID: 39)
LEAGUE_ID = 1023  # Premier League ID

# Automatically get the current year for the season
SEASON = time.localtime()[0]  # Use the current year from the system

# Function to convert UTC time string (HH:MM) to local time (considering BST/GMT)
def convert_utc_to_local(utc_time_str):
    hour_utc, minute = map(int, utc_time_str.split(":"))
    local_time = time.localtime()
    time_offset = 1 if is_bst(local_time) else 0  # BST (UTC+1) if DST is active, otherwise GMT (UTC+0)
    hour_local = (hour_utc + time_offset) % 24
    return f"{hour_local:02d}:{minute:02d}"

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

# Async function to connect to Wi-Fi
async def connect_wifi(timeout=30):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    start_time = time.time()
    
    gc.collect()  # Clean up memory before starting the connection process
    
    while not wlan.isconnected():
        if time.time() - start_time > timeout:
            print("Failed to connect to Wi-Fi within timeout.")
            return False
        await asyncio.sleep(1)
    
    print("Connected to Wi-Fi")
    return True

# Async function to fetch the current league standings
async def fetch_standings():
    gc.collect()  # Free memory before making the request
    url = f'https://v3.football.api-sports.io/standings?league={LEAGUE_ID}&season={SEASON}'
    headers = {'x-apisports-key': API_KEY}
    
    try:
        response = urequests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            standings = data['response'][0]['league']['standings'][0]
            positions = {team['team']['id']: team['rank'] for team in standings}
        else:
            print("Failed to fetch standings:", response.status_code)
            positions = {}
    finally:
        response.close()
        gc.collect()  # Free memory after handling the response
    
    return positions

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
                details.append(f"Goal: {scorer} ({event['time']['elapsed']}')")
            elif event['type'] == 'Card':
                card_type = 'Yellow' if event['detail'] == 'Yellow Card' else 'Red'
                card_color = YELLOW if card_type == 'Yellow' else RED
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


# Function to load and display team crests
def load_and_display_crest(team_id, x, y):
    gc.collect()  # Clean up memory before loading images
    
    crest_filename = f"/sd/{team_id}.png"
    try:
        os.stat(crest_filename)  # Check if the file exists
        png.open_file(crest_filename)  # Open the PNG file
        png.decode(x, y)  # Decode and display at the given coordinates
    except OSError:
        # If the file does not exist, draw a black square as a fallback
        display.set_pen(BLACK)
        display.rectangle(x, y, 20, 20)

# Function to fetch fixtures for today and upcoming days until a total of 10 is reached
async def fetch_and_display_fixtures(positions):
    gc.collect()  # Free memory before fetching fixtures
    y_position = 10  # Starting y-position for the first day's fixtures
    base_line_height = 40  # Base space between rows to fit more fixtures

    total_fixtures_to_display = 10
    displayed_fixtures = []  # To store all fixtures
    today_date = "{:04d}-{:02d}-{:02d}".format(*time.localtime()[:3])  # Get today's date
    matchday_offset = 0  # Start from today and move forward if needed

    while len(displayed_fixtures) < total_fixtures_to_display:
        # Fetch fixtures for the current matchday
        url = f'https://v3.football.api-sports.io/fixtures?league={LEAGUE_ID}&season={SEASON}&date={today_date}'
        headers = {'x-apisports-key': API_KEY}
        response = urequests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            fixtures = data['response']
            
            # Append today's matches
            for fixture in fixtures:
                displayed_fixtures.append(fixture)
                if len(displayed_fixtures) >= total_fixtures_to_display:
                    break

        else:
            print(f"Failed to fetch fixtures for {today_date}: {response.status_code}")
            break

        # If fewer than 10 fixtures were found, increment the matchday_offset for the next day
        matchday_offset += 1
        today_date = "{:04d}-{:02d}-{:02d}".format(*time.localtime(time.time() + (matchday_offset * 86400))[:3])

    # Sort fixtures by their timestamp to ensure correct time order
    displayed_fixtures = sorted(displayed_fixtures, key=lambda fixture: fixture['fixture']['timestamp'])

    # Now display the fixtures
    if len(displayed_fixtures) == 0:
        display.set_pen(RED)
        display.text("No fixtures found.", 10, y_position, scale=2)
    else:
        current_date = None  # Track current date for grouping fixtures by match day
        for fixture in displayed_fixtures:
            fixture_id = fixture['fixture']['id']
            fixture_time_utc = fixture['fixture']['date'][11:16]  # Time of the fixture (HH:MM) in UTC
            fixture_date = fixture['fixture']['date'][:10]  # Extract the YYYY-MM-DD part of the date

            print(f"Displaying fixture: {fixture_id}, Time: {fixture_time_utc}")

            # Convert fixture date to DD-MM-YYYY format
            date_parts = fixture_date.split('-')
            fixture_date_formatted = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"

            # Function to get the day name from a date (YYYY-MM-DD format)
            def get_day_name(date_str):
                year, month, day = map(int, date_str.split('-'))
                date_tuple = (year, month, day, 0, 0, 0, 0, 0)
                timestamp = time.mktime(date_tuple)
                weekday_num = time.localtime(timestamp)[6]
                day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                return day_names[weekday_num]

            # Display the day name and date header if the fixture's date is different from the current one
            if fixture_date != current_date:
                current_date = fixture_date
                day_name = get_day_name(fixture_date)
                header_text = f"{day_name}, {fixture_date_formatted}"

                display.set_pen(BLUE)
                display.text(header_text, 10, y_position, scale=1)
                y_position += 10
                display.line(0, y_position, display.get_bounds()[0], y_position)
                y_position += 10

            # Convert UTC time to local time
            fixture_time_local = convert_utc_to_local(fixture_time_utc)
            print(f"Fixture local time: {fixture_time_local}")

            home_team = fixture['teams']['home']['name']
            away_team = fixture['teams']['away']['name']
            home_team_id = fixture['teams']['home']['id']
            away_team_id = fixture['teams']['away']['id']
            home_score = fixture['goals']['home']
            away_score = fixture['goals']['away']
            status = fixture['fixture']['status']['short']

            # Determine how to display the score and status
            if status == 'FT':  # Full Time
                score_display = f"{home_score}-{away_score}"
                pen_color = BLACK
            elif status in ['LIVE', '1H', '2H', 'HT']:  # Match in progress
                score_display = f"{home_score}-{away_score}"  # Show only the score, without marking as LIVE
                pen_color = GREEN  # Indicate live matches in green
            elif status == 'NS':  # Match Not Started
                score_display = fixture_time_local  # Display the start time for not started matches
                pen_color = RED  # Show upcoming matches in red
            elif status == 'TBD':  # Time to be decided
                score_display = "TBD"  # Show "TBD" if the time is not determined
                pen_color = RED
            else:  # Other statuses (e.g., postponed or canceled)
                score_display = "P-P"
                pen_color = RED

            print(f"Score display: {score_display}")

            score_x = 240
            score_width = display.measure_text(score_display, scale=2)
            home_crest_x = score_x - score_width // 2 - 27
            home_team_name_x = home_crest_x - display.measure_text(home_team[:17], scale=2) - 5

            # Display home team
            if home_team_id in positions:
                league_position = str(positions[home_team_id])
                superscript_x_home = home_team_name_x - display.measure_text(league_position, scale=1) - 3
                display.set_pen(RED)
                display.text(league_position, superscript_x_home, y_position - 3, scale=1)

            display.set_pen(BLACK)
            display.text(f"{home_team[:17]}", home_team_name_x, y_position + 5, scale=2)
            load_and_display_crest(home_team_id, home_crest_x, y_position + 2)

            # Display time/score
            display.set_pen(pen_color)
            display.text(score_display, score_x - score_width // 2, y_position + 5, scale=2)

            # Display away team
            away_crest_x = score_x + score_width // 2 + 5
            away_team_name_x = away_crest_x + 20 + 5

            load_and_display_crest(away_team_id, away_crest_x, y_position + 2)
            display.set_pen(BLACK)
            display.text(f"{away_team[:17]}", away_team_name_x, y_position + 5, scale=2)

            if away_team_id in positions:
                league_position = str(positions[away_team_id])
                superscript_x_away = away_team_name_x + display.measure_text(away_team[:17], scale=2) + 3
                display.set_pen(RED)
                display.text(league_position, superscript_x_away, y_position - 3, scale=1)

            # Fetch and display match details like goal scorers and cards
            details = await fetch_fixture_events(fixture_id)
            detail_x_offset = 515  # X-position for details
            wrapped_lines = wrap_text("; ".join(details), 63)

            # Calculate vertical offset for centering the wrapped lines
            total_lines = len(wrapped_lines)
            vertical_offset = ((total_lines - 1) * 10) // 2 - 8

            # Display each wrapped line
            for i, line in enumerate(wrapped_lines):
                display.set_pen(BLACK)
                display.text(line, detail_x_offset, y_position - vertical_offset + (i * 10), scale=1)

            # Adjust y_position for the next fixture, considering the number of wrapped lines
            y_position += base_line_height + (total_lines - 1) * 8

        y_position += 5  # Extra space after finishing a day's fixtures


# Main function to run all tasks
async def main():
    gc.collect()  # Clean memory before starting the main process
    wifi_connected = await connect_wifi()  # Attempt to connect to Wi-Fi
    if not wifi_connected:
        print("Exiting due to Wi-Fi failure.")
        return  # Exit if Wi-Fi couldn't be connected
    
    positions = await fetch_standings()  # Fetch the league standings
    await fetch_and_display_fixtures(positions)  # Fetch and display fixtures with league positions
    
    # Update the display after drawing everything
    display.update()
    
    # Final garbage collection
    gc.collect()


# Run the main function
asyncio.run(main())

