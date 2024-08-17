# pimoroni-inky-footy-frame
premier league league table and fixtures lists with live scores and match details, displaying on Pimoroni's e-ink colour display, The Inky Frame 7.3

(this is in a very alpha stage atm, but i wanted to share it on the information super highway for others to utilise and play with.

give me a follow on all the socials @mrglennjones. let me know if you like/hate it or just send me some classic footy hooligan style banter or abuse, whatever.

![image](https://github.com/user-attachments/assets/9ef435da-9ec8-4ad1-b0a5-c6c2f4ba852a)
![image](https://github.com/user-attachments/assets/04c89abf-9905-4ba1-87b0-c86cf1205b86)


## required:-
- Pimoroni Inky Frame 7.3 (smaller ones will need extension code adjustment for resizing this to a smaller e-ink display)
https://shop.pimoroni.com/products/inky-frame-7-3?variant=40541882056787

- wifi/internet connection

- https://www.api-football.com/ account (this makes saeveral calls to the this api, theres 100 calls per day available on the free tier, so be careful with overuse (check the their dashboard for current usage totals)

## recomended:-
- Micro SD card for team crest png image storage (default)
you could adjust the code and store them on the pico if required. (should fit) :)


## guide:-

these scripts utilise data fetched from https://www.api-football.com/
create an account here https://dashboard.api-football.com/register

1. copy and paste your API KEY to a file called [API KEY FILE](API_KEY.py) and save it to the root of the pico, with the contents:-

```
API_KEY = 'your api key here'
```
2. create a file WIFI_CONFIG.py also in the root of the pico and enter your wifi details:-
```
SSID = "your wifi ssid"
PASSWORD = "your wifi password"
COUNTRY = "GB"  # Change to your local two-letter ISO 3166-1 country code
```
3. copy all of the crest png files from [crest png images](footy_frame_crests.zip) to the root (not in a folder) of the sd card (or pico if you've adjusted the code)

4. run league_standings.py - this displays a full premier league table along with form data and team crest pngs
5. or run match_fixtures.py - this displays 3 days of premier league fixtures along with, live scores and match details



### ill put todo stuff in the issues section, feel free to get involved and collaberate on this.

G
