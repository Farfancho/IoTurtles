from pathlib import Path
from smbus2 import SMBus, i2c_msg
import time

# CONFIGURACIÓN

I2C_BUS = 1

SHT3X_ADDRESS = 0x44
MLX90614_ADDRESS = 0x5A

MLX_AMBIENT_REGISTER = 0x06
MLX_OBJECT_REGISTER = 0x07

W1_PATH = Path("/sys/bus/w1/devices")

READ_INTERVAL = 1.0

# DS18B20

def findDS18B20():
    sensors = list(W1_PATH.glob("28-*"))    

    if not sensors:
        raise RuntimeError("No se encontró el DS18B20")

    return sensors[0]


def readDS18B20(sensorPath):
    dataFile = sensorPath / "w1_slave"

    with open(dataFile, "r") as file:
        lines = file.readlines()

    # Verificar 
    if not lines[0].strip().endswith("YES"):
        raise RuntimeError("CRC incorrecto en DS18B20")

    temperaturePosition = lines[1].find("t=")

    if temperaturePosition == -1:
        raise RuntimeError("No se encontró temperatura en DS18B20")

    rawTemperature = lines[1][temperaturePosition + 2:]

    temperature = float(rawTemperature) / 1000.0

    return temperature

# SHT3x

def calculateSHT3xCrc(data):
    crc = 0xFF

    for byte in data:
        crc ^= byte

        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ 0x31
            else:
                crc <<= 1

            crc &= 0xFF

    return crc


def readSHT3x(bus):
    # Single-shot
    # Alta repetibilidad
    # Clock stretching deshabilitado
    command = i2c_msg.write(
        SHT3X_ADDRESS,
        [0x24, 0x00]
    )

    bus.i2c_rdwr(command)

    # La medición puede tardar hasta 15 ms
    time.sleep(0.02)

    # T_MSB, T_LSB, CRC, RH_MSB, RH_LSB, CRC
    readMessage = i2c_msg.read(SHT3X_ADDRESS, 6)

    bus.i2c_rdwr(readMessage)

    data = list(readMessage)

    # Verificar CRC de temperatura
    if calculateSHT3xCrc(data[0:2]) != data[2]:
        raise RuntimeError("CRC incorrecto en temperatura SHT3x")

    # Verificar CRC de humedad
    if calculateSHT3xCrc(data[3:5]) != data[5]:
        raise RuntimeError("CRC incorrecto en humedad SHT3x")

    rawTemperature = (data[0] << 8) | data[1]
    rawHumidity = (data[3] << 8) | data[4]

    temperature = -45 + (175 * rawTemperature / 65535)
    humidity = 100 * rawHumidity / 65535

    return temperature, humidity

# MLX90614

def readMLXTemperature(bus, register):
    rawValue = bus.read_word_data(
        MLX90614_ADDRESS,
        register
    )

    # Bit 15 indica error
    if rawValue & 0x8000:
        raise RuntimeError("MLX90614 reportó error")

    rawValue &= 0x7FFF

    temperature = (rawValue * 0.02) - 273.15

    return temperature


def readMLX90614(bus):
    ambientTemperature = readMLXTemperature(
        bus,
        MLX_AMBIENT_REGISTER
    )

    objectTemperature = readMLXTemperature(
        bus,
        MLX_OBJECT_REGISTER
    )

    return ambientTemperature, objectTemperature

def main():
    print("Buscando DS18B20...")
    ds18b20Path = findDS18B20()
    print(f"DS18B20 encontrado: {ds18b20Path.name}")
    print("Iniciando sensores...\n")
    with SMBus(I2C_BUS) as bus:
        try:
            while True:
                # DS18B20
                try:
                    dsTemperature = readDS18B20(ds18b20Path)
                    dsText = f"{dsTemperature:.2f} °C"
                except Exception as error:
                    dsText = f"ERROR ({error})"
                # SHT3x
                try:
                    shtTemperature, humidity = readSHT3x(bus)
                    shtText = (
                        f"{shtTemperature:.2f} °C | "
                        f"{humidity:.2f} %RH"
                    )
                except Exception as error:
                    shtText = f"ERROR ({error})"
                # MLX90614
                try:
                    mlxAmbient, mlxObject = readMLX90614(bus)
                    mlxText = (
                        f"Ambiente: {mlxAmbient:.2f} °C | "
                        f"Objeto: {mlxObject:.2f} °C"
                    )
                except Exception as error:
                    mlxText = f"ERROR ({error})"
                print("----------------------------------------")
                print(f"DS18B20 : {dsText}")
                print(f"SHT3x   : {shtText}")
                print(f"MLX90614: {mlxText}")
                time.sleep(READ_INTERVAL)
        except KeyboardInterrupt:
            print("\nLectura finalizada.")  

if __name__ == "__main__":
    main()