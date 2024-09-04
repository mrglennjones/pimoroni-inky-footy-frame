from machine import ADC, Pin
import time
from picographics import PicoGraphics, DISPLAY_INKY_FRAME_7

def display_battery(display):
    # these are our reference voltages for a full/empty battery, in volts
    full_battery = 4.2
    empty_battery = 2.8

    # colours to draw with
    BLACK = 0
    WHITE = 1
    GREEN = 2
    BLUE = 3
    RED = 4
    ORANGE = 6
    YELLOW = 5

    # set up the display
    display = PicoGraphics(display=DISPLAY_INKY_FRAME_7)

    # and the activity LED
    activity_led = Pin(6, Pin.OUT)
    activity_led.on()

    # set up and enable vsys hold so Inky Frame doesn't go to sleep
    HOLD_VSYS_EN_PIN = 2

    hold_vsys_en_pin = Pin(HOLD_VSYS_EN_PIN, Pin.OUT)
    hold_vsys_en_pin.value(True)

    # set up the ADC that's connected to the system input voltage (VSYS)
    vsys = ADC(3)  # Use ADC3 (GPIO29)

    # on a Pico W we need to pull GP25 high to be able to read vsys
    spi_output = Pin(25, Pin.OUT)
    spi_output.value(True)

    # how we convert the reading into a voltage, and then a percentage
    conversion_factor = 3 * 3.3 / 65535
         
    # convert the raw ADC read into a voltage, and then a percentage
    voltage = vsys.read_u16() * conversion_factor
    percentage = 100 * ((voltage - empty_battery) / (full_battery - empty_battery))
    if percentage > 100:
        percentage = 100.00

    # monitoring vbus tells us if Inky is being USB powered
    vbus = Pin('WL_GPIO2', Pin.IN)

    # New coordinates and sizes for repositioned battery graphic
    battery_width = 38  # Adjusted to maintain aspect ratio with the new height
    battery_height = 13
    battery_x = 800 - battery_width - 12  # 8 pixels padding from the right edge
    battery_y = 2  # 5 pixels padding from the top edge

    # clear the display
    display.set_pen(WHITE)
    display.clear()

    # draw the battery outline with a hollow white interior
    display.set_pen(BLACK)
    display.rectangle(battery_x, battery_y, battery_width, battery_height)  # Main battery body outline
    display.rectangle(battery_x + battery_width, battery_y + 4, 3, 5)  # Battery "nub" on the right

    display.set_pen(WHITE)
    display.rectangle(battery_x + 1, battery_y + 1, battery_width - 2, battery_height - 2)  # Hollow interior

    # set the pen color based on the battery percentage for the level indicator
    if percentage >= 40:
        display.set_pen(GREEN)
    elif percentage >= 20:
        display.set_pen(ORANGE)
    else:
        display.set_pen(RED)

    # draw the battery level indicator inside the battery
    display.rectangle(battery_x + 2, battery_y + 2, round((battery_width - 4) * (percentage / 100)), battery_height - 4)

    # add text next to the battery graphic
    if vbus.value():
        display.set_pen(BLUE)
        display.text('USB', battery_x - 50, battery_y, 240, 2)
    else:
        display.set_pen(BLACK)
        display.text('{:.0f}%'.format(percentage), battery_x - 40, battery_y , 240, 2)

    #display.update() #handled by hosting script

    # go to sleep until someone pushes a button
    activity_led.off()
    hold_vsys_en_pin.init(Pin.IN)

if __name__ == "__main__":
    display_battery()

