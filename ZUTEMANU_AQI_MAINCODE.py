import bme680
import time
import requests

temperature = 0
humidity = 0
pressure = 0
gas_resistance = 0
AQI_score = 0
AQI_level = ""
hum_reference = 40
gas_reference = 2500
try:
    sensor = bme680.BME680(bme680.I2C_ADDR_PRIMARY)
except (RuntimeError, IOError):
    sensor = bme680.BME680(bme680.I2C_ADDR_SECONDARY)

# These calibration data can safely be commented
# out, if desired.

print('Calibration data:')
for name in dir(sensor.calibration_data):

    if not name.startswith('_'):
        value = getattr(sensor.calibration_data, name)

        if isinstance(value, int):
            print('{}: {}'.format(name, value))

# These oversampling settings can be tweaked to
# change the balance between accuracy and noise in
# the data.
sensor.set_humidity_oversample(bme680.OS_2X)
sensor.set_pressure_oversample(bme680.OS_4X)
sensor.set_temperature_oversample(bme680.OS_8X)
sensor.set_filter(bme680.FILTER_SIZE_3)
sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)

print('\n\nInitial reading:')
for name in dir(sensor.data):
    value = getattr(sensor.data, name)

    if not name.startswith('_'):
        print('{}: {}'.format(name, value))

sensor.set_gas_heater_temperature(320)
sensor.set_gas_heater_duration(150)
sensor.select_gas_heater_profile(0)

def send_to_ubidots(payload):
    url = "https://industrial.api.ubidots.com/api/v1.6/devices/bme680"
    headers = {
        "Content-Type": "application/json",
        "X-Auth-Token": "BBFF-ha9Yzk9zFNMZL21MHBTdKSms4ffDYX"
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print("Data berhasil diunggah ke Ubidots")
    else:
        print("Gagal mengunggah data ke Ubidots. Kode status:", response.status_code)
        
#calculate humidity score 
def humidity_score(humidity_value):
    if humidity_value >=38 and humidity_value <= 42:
        hum_score = 0.25 * 100
    else:
        if humidity_value < 38:
            hum_score = 0.25/hum_reference*humidity_value*100
        else:
            hum_score = ((-0.25/(100-hum_reference)*humidity_value)+0.416666)*100
    return hum_score

#calculate gas score 
gas_lower_limit = 5000  #good quality
gas_upper_limit = 50000 #bad quality

def get_gas_reference(gas_resistance):
    global gas_reference
    readings = 10
    for i in range(1, readings):  # read gas for 10 x 0.150mS = 1.5secs
        gas_reference += gas_resistance
    gas_reference = gas_reference / readings
    #print("Gas Reference =", round(gas_reference, 3))
    return gas_reference

def get_gas_score():
    # Calculate gas contribution to IAQ index
    gas_score = (0.75 / (gas_upper_limit - gas_lower_limit) * gas_reference - (gas_lower_limit * (0.75 / (gas_upper_limit - gas_lower_limit)))) * 100.00
    if gas_score > 75:  # Sometimes gas readings can go outside of the expected scale maximum
        gas_score = 75
    if gas_score < 0:  # Sometimes gas readings can go outside of the expected scale minimum
        gas_score = 0

    return gas_score

def calculate_IAQ(score):
    IAQ_text = "air quality is "
    score = (100 - score) * 5

    if score >= 301:
        IAQ_text += "Hazardous"
    elif 201 <= score <= 300:
        IAQ_text += "Very Unhealthy"
    elif 176 <= score <= 200:
        IAQ_text += "Unhealthy"
    elif 151 <= score <= 175:
        IAQ_text += "Unhealthy for Sensitive Groups"
    elif 51 <= score <= 150:
        IAQ_text += "Moderate"
    elif 0 <= score <= 50:
        IAQ_text += "Good"

    return IAQ_text

print('\n\nPolling:')
try:
    while True:
        
        if sensor.get_sensor_data():
            temperature = sensor.data.temperature
            pressure = sensor.data.pressure
            humidity = sensor.data.humidity
            output = '\n temperature : {0:.2f} C \npressure : {1:.2f} hPa \n humidity: {2:.2f} %'.format(
                temperature,
                pressure,
                humidity)
            if sensor.data.heat_stable:
                gas_resistance = sensor.data.gas_resistance
                get_gas_reference(gas_resistance)
                hum_score = humidity_score(humidity)
                gas_score      = get_gas_score()
                air_quality_score = hum_score + gas_score
                IAQ_text = calculate_IAQ(air_quality_score)
                print('Humidity score :', hum_score)
                print('Gas score :', gas_score)
                print('Air quality score :', air_quality_score)
                print('Air quality in room is ' + IAQ_text)
                print('{0} \n gas resistance : {1} Ohms'.format(
                    output,
                    gas_resistance))
                payload = {
                "temperature": temperature,
                "humidity": humidity,
                "pressure": pressure,
                "gas": gas_resistance,
                "air_quality_score": air_quality_score
                }
                send_to_ubidots(payload)
            else:
                print(output)

        time.sleep(2)

except KeyboardInterrupt:
    pass