import network
import urequests
import time
import os
import machine
import sdcard
from machine import Pin, SPI
from picographics import PicoGraphics, DISPLAY_INKY_FRAME_7, PEN_P4
from pngdec import PNG

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

# Wi-Fi Connection
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PASSWORD)

# Wait for connection
while not wlan.isconnected():
    time.sleep(1)
print("Connected to Wi-Fi")

# Set up the SD card
sd_spi = SPI(0, sck=Pin(18, Pin.OUT), mosi=Pin(19, Pin.OUT), miso=Pin(16, Pin.OUT))
sd = sdcard.SDCard(sd_spi, machine.Pin(22))
os.mount(sd, "/sd")

# Fetch Premier League data
LEAGUE_ID = 39  # Premier League ID
SEASON = 2024  # Current season
url = f'https://v3.football.api-sports.io/standings?league={LEAGUE_ID}&season={SEASON}'
headers = {
    'x-apisports-key': API_KEY
}

response = urequests.get(url, headers=headers)

# Check if the response is OK
if response.status_code == 200:
    data = response.json()
    standings = data['response'][0]['league']['standings'][0]

    # Extract league details
    league_table = []
    for team in standings:
        league_table.append({
            'position': team['rank'],
            'name': team['team']['name'],
            'id': team['team']['id'],  # Use the team ID directly
            'played': team['all']['played'],
            'wins': team['all']['win'],
            'draws': team['all']['draw'],
            'losses': team['all']['lose'],
            'goals_for': team['all']['goals']['for'],
            'goals_against': team['all']['goals']['against'],
            'goal_difference': team['goalsDiff'],
            'points': team['points'],
            'form': team['form']
        })

    # Clear the display
    display.set_pen(WHITE)
    display.clear()

    # Set the font to bitmap8
    display.set_font("bitmap8")

    # Draw column headers (shifted 20 pixels to the right)
    display.set_pen(BLACK)
    display.text("Team", 60, 5, scale=2)
    display.text("P", 235, 5, scale=2)   # Shifted by 20px
    display.text("W", 295, 5, scale=2)   # Shifted by 20px
    display.text("D", 355, 5, scale=2)   # Shifted by 20px
    display.text("L", 415, 5, scale=2)   # Shifted by 20px
    display.text("GF", 475, 5, scale=2)  # Shifted by 20px
    display.text("GA", 535, 5, scale=2)  # Shifted by 20px
    display.text("GD", 595, 5, scale=2)  # Shifted by 20px
    display.text("Pts", 655, 5, scale=2) # Shifted by 20px
    display.text("Form", 725, 5, scale=2)

    # Start drawing the teams' data
    y_position = 30  # Start position below headers
    line_height = 22  # Reduced space between rows

    for i, team in enumerate(league_table):
        x_offset = 5  # Offset for left margin

        # Draw lines to separate European qualification and relegation places
        if i == 4:  # Top 4 teams (Champions League qualification)
            display.set_pen(BLUE)
            display.line(x_offset, y_position - 5, 790, y_position - 5)

        if i == 5:  # Top 5 teams (Europa League/Conference League qualification)
            display.set_pen(BLUE)
            display.line(x_offset, y_position - 5, 790, y_position - 5)

        if i == 17:  # Bottom 3 teams (relegation)
            display.set_pen(RED)
            display.line(x_offset, y_position - 5, 790, y_position - 5)

        # Draw Team Position (shifted after crest column)
        display.set_pen(BLACK)
        display.text(f"{team['position']}.", x_offset, y_position, scale=2)

        # Load and draw the team crest using pngdec, using team ID as filename
        crest_filename = f"/sd/{team['id']}.png"
        try:
            with open(crest_filename, 'rb'):
                png.open_file(crest_filename)
                png.decode(x_offset+30, y_position-3)  # Position the PNG at the current offset and y position
        except OSError:
            print(f"Crest file not found: {crest_filename}")
        except Exception as e:
            print(f"Error loading crest {crest_filename}: {e}")

        # Team Name (shifted after position and crest)
        display.set_pen(BLACK)
        display.text(f"{team['name'][:17]}", x_offset + 55, y_position, scale=2)

        # Matches Played, Wins, Draws, Losses, Goals For, Goals Against, Goal Difference, Points
        display.text(f"{team['played']}", 235, y_position, scale=2)   # Shifted by 20px
        display.text(f"{team['wins']}", 295, y_position, scale=2)     # Shifted by 20px
        display.text(f"{team['draws']}", 355, y_position, scale=2)    # Shifted by 20px
        display.text(f"{team['losses']}", 415, y_position, scale=2)   # Shifted by 20px
        display.text(f"{team['goals_for']}", 475, y_position, scale=2)# Shifted by 20px
        display.text(f"{team['goals_against']}", 535, y_position, scale=2) # Shifted by 20px
        display.text(f"{team['goal_difference']}", 595, y_position, scale=2)# Shifted by 20px
        display.text(f"{team['points']}", 655, y_position, scale=2)   # Shifted by 20px

        # Team Form (Color Coded with Letters)
        form_x_offset = 720  # Shifted by 20px
        for j, result in enumerate(team['form']):
            if result == 'W':
                display.set_pen(GREEN)  # Win
            elif result == 'L':
                display.set_pen(RED)  # Loss
            elif result == 'D':
                display.set_pen(GRAY)  # Draw
            
            # Draw a smaller square representing the form
            display.rectangle(form_x_offset + (j * 16), y_position, 14, 14)
            
            # Draw the W, D, L letters inside the square
            display.set_pen(WHITE)
            display.text(result, form_x_offset + (j * 16) + 2, y_position + 2, scale=1)

        # Update the y_position for the next team
        y_position += line_height

    # Draw final relegation line
    display.set_pen(RED)
    display.line(x_offset, y_position - 5, 790, y_position - 5)

    # Update the display
    display.update()

else:
    print("Failed to fetch data:", response.status_code)

response.close()

# Unmount the SD card
#os.umount("/sd")
#print("SD card unmounted.")

