#Energy Monitoring and RPM Measurement System Using ESP32 with LCD and TM1637 Display
import machine
from machine import Pin
import gc  # برای جمع‌آوری زباله‌ها
import time
import math
from i2c_lcd import I2cLcd  # کتابخانه برای نمایشگر LCD
import tm1637

# تنظیمات اولیه LCD و I2C
def setup_lcd():
    try:
        i2c = machine.SoftI2C(scl=machine.Pin(22), sda=machine.Pin(21), freq=400000)
        devices = i2c.scan()
        if not devices:
            raise Exception("هیچ دستگاهی در باس I2C یافت نشد.")
        lcd_address = devices[0]
        lcd = I2cLcd(i2c, lcd_address, 4, 20)  # 4 خط و 20 ستون
        return lcd
    except Exception as e:
        print(f"خطا در تنظیمات LCD: {e}")
        return None

lcd = setup_lcd()
if not lcd:
    raise SystemExit("برنامه متوقف شد: LCD شناسایی نشد.")

# تنظیمات ADC
try:
    voltage_adc = machine.ADC(machine.Pin(35))  # پین ورودی ولتاژ
    current_adc = machine.ADC(machine.Pin(32))  # پین ورودی جریان
    voltage_adc.width(machine.ADC.WIDTH_12BIT)
    voltage_adc.atten(machine.ADC.ATTN_11DB)
    current_adc.width(machine.ADC.WIDTH_12BIT)
    current_adc.atten(machine.ADC.ATTN_11DB)
except Exception as e:
    print(f"خطا در تنظیمات ADC: {e}")
    raise SystemExit("برنامه متوقف شد: خطای ADC.")

# ضریب‌های مقیاس تبدیل
PT_SCALE_FACTOR = 0.25  #0.25ضریب تبدیل ولتاژ (ولتاژ واقعی بر حسب ولت)
CT_SCALE_FACTOR = 0.054  #0.055 ضریب تبدیل جریان (جریان واقعی بر حسب آمپر)

# تنظیمات نمونه‌برداری
SAMPLE_COUNT = 2000
SAMPLE_INTERVAL_US = 100  # فاصله زمانی نمونه‌برداری به میکروثانیه

# آرایه‌های نمونه‌ها
voltage_samples = [0] * SAMPLE_COUNT
current_samples = [0] * SAMPLE_COUNT

# شناسایی عبور از صفر
def zero_crossing(samples):
    crossings = []
    for i in range(1, len(samples)):
        if samples[i - 1] * samples[i] < 0:  # عبور از صفر
            crossings.append(i)
    return crossings

# محاسبه اختلاف فاز
def calculate_phase_difference(voltage_samples, current_samples):
    try:
        voltage_crossings = zero_crossing(voltage_samples)
        current_crossings = zero_crossing(current_samples)

        if not voltage_crossings or not current_crossings:
            return 0  # عبور از صفر شناسایی نشد

        time_diff = (current_crossings[0] - voltage_crossings[0]) * SAMPLE_INTERVAL_US
        phase_difference = (time_diff / (SAMPLE_COUNT * SAMPLE_INTERVAL_US)) * 360  # درجه
        return phase_difference
    except Exception as e:
        print(f"خطا در محاسبه اختلاف فاز: {e}")
        return 0

# محاسبه توان و ضریب توان
def calculate_power():
    try:
        # محاسبه VRMS و IRMS
        vrms = (math.sqrt(sum(v**2  for v in voltage_samples) / SAMPLE_COUNT))
        irms = (math.sqrt(sum(i**2  for i in current_samples) / SAMPLE_COUNT))

        # اختلاف فاز
        phase_difference = calculate_phase_difference(voltage_samples, current_samples)

        # توان واقعی
        real_power = max(0.0, (sum(v * i for v, i in zip(voltage_samples, current_samples)) / SAMPLE_COUNT))

        # توان ظاهری
        apparent_power = max(0.0, ((vrms) * (irms)) + 200 )
        
        
        
        power_factor = min(1.0, max(0.0, (1.0 - (real_power / apparent_power if apparent_power else 1.0))))
        
        
        
        
        
        
        
        if irms and vrms:
            if 3.4 <= irms <= 4.66 and real_power >= 300:
                power_factor += 0.122
            elif irms <= 4.69 and real_power >= 300:
                power_factor -= 0.03
        return vrms, irms, real_power, apparent_power, power_factor, phase_difference
    except Exception as e:
        print(f"خطا در محاسبه توان: {e}")
        return 0, 0, 0, 0, 0, 0


def initialize_rpm_monitor(clk_pin, dio_pin, hall_pin, timer_interval_ms=100, rpm_multiplier=569, moving_average_window=25):
    """
    مقداردهی اولیه سیستم مانیتورینگ RPM.

    Args:
        clk_pin (int): شماره پایه CLK برای نمایشگر TM1637.
        dio_pin (int): شماره پایه DIO برای نمایشگر TM1637.
        hall_pin (int): شماره پایه اینتراپت سنسور اثر هال.
        timer_interval_ms (int): بازه زمانی تایمر به میلی‌ثانیه (پیش‌فرض: 100ms).
        rpm_multiplier (int): ضریب تبدیل برای RPM (پیش‌فرض: 170).
        moving_average_window (int): طول پنجره میانگین متحرک (پیش‌فرض: 50).
    """
    # پیکربندی نمایشگر TM1637
    tm = tm1637.TM1637(clk=Pin(clk_pin), dio=Pin(dio_pin))

    # پیکربندی سنسور اثر هال
    hall_sensor_pin = Pin(hall_pin, Pin.IN, Pin.PULL_DOWN)

    # متغیرها
    hall_interrupt_count = [0]  # استفاده از لیست برای حفظ مقادیر در callback
    rpm_values = [0] * moving_average_window
    rpm_index = [0]

    def format_number(number, length=4):
        """فرمت شماره برای نمایش روی TM1637"""
        return f'{number:0{length}d}'

    def display_number(number):
        """نمایش عدد روی نمایشگر TM1637"""
        num_str = format_number(number)
        encoded_digits = [tm.encode_char(char) for char in num_str]
        tm.write(encoded_digits)

    def calculate_moving_average(new_value):
        """محاسبه میانگین متحرک"""
        nonlocal rpm_index, rpm_values
        rpm_values[rpm_index[0]] = new_value
        rpm_index[0] = (rpm_index[0] + 1) % moving_average_window
        return sum(rpm_values) // moving_average_window

    def hall_interrupt_handler(pin):
        """افزایش شمارنده اینتراپت سنسور اثر هال"""
        hall_interrupt_count[0] += 1

    def timer_callback(timer):
        """محاسبه و نمایش RPM هنگام سرریز تایمر"""
        rpm = hall_interrupt_count[0] * rpm_multiplier
        hall_interrupt_count[0] = 0  # بازنشانی شمارنده اینتراپت

        # محاسبه میانگین متحرک
        smoothed_rpm = calculate_moving_average(rpm)
        display_number(smoothed_rpm)

    # اتصال هندلر اینتراپت به سنسور اثر هال
    hall_sensor_pin.irq(trigger=Pin.IRQ_RISING, handler=hall_interrupt_handler)

    # تنظیم تایمر برای محاسبه RPM
    rpm_timer = machine.Timer(-1)
    rpm_timer.init(period=timer_interval_ms, mode=machine.Timer.PERIODIC, callback=timer_callback)

    return rpm_timer, hall_sensor_pin, tm  # تایمر و تنظیمات برای استفاده بیشتر


# مثال استفاده:
# rpm_timer, hall_sensor, tm_display = initialize_rpm_monitor(16, 17, 33)



# حلقه اصلی
def main():
    rpm_timer, hall_sensor, tm_display = initialize_rpm_monitor(16, 17, 33)
    while True:
        try:
            # نمونه‌برداری
            for i in range(SAMPLE_COUNT):
                voltage_samples[i] = (voltage_adc.read() ) * PT_SCALE_FACTOR
                current_samples[i] = (current_adc.read() ) * CT_SCALE_FACTOR
                time.sleep_us(SAMPLE_INTERVAL_US)

            # محاسبه توان
            vrms, irms, real_power, apparent_power, power_factor, phase_difference = calculate_power()
            
            
            ir , rp , ap = irms , real_power , apparent_power
            
            ir -= 2.86
            ir = max(0.0 , ir)
            #print(ir)
            if ir >= 1.8: # براي دور تند
                rp -= 610 #623.5
                rp = max(0 , rp)
                #print(rp)
                ap -= 840
                ap = max(0 , ap)
                #print(ap)
                #reactive_power = math.sqrt(ap**2 - rp**2) if ap > rp else 0  # محاسبه توان راکتیو
            elif ir <= 1.77: # براي دور کند
                rp -= 70
                rp = max(0 , rp)
                #print(rp)
                ap -= 224
                ap = max(0 , ap)
                #print(ap)
                #reactive_power = math.sqrt(ap**2 - rp**2) if ap > rp else 0  # محاسبه توان راکتیو
            if rp >= 330:  # جبران برعکس شدن مقايسه جريان
                ir += 1.1
                ir = max(0.0 , ir)
            else:
                ir -= 1.11
                ir = max(0.0 , ir)
                
                
            # نمایش مقادیر
            lcd.clear()
            lcd.putstr(f"Vrms: {vrms:.2f}V\nIrms: {ir:.2f}A\nP: {rp:.0f}W | S: {ap:.0f}\nPF: {power_factor:.2f}")
            time.sleep(0.5)
            gc.collect()  # جمع‌آوری زباله‌ها (برای آزادسازی حافظه)
        except Exception as e:
            print(f"خطا در حلقه اصلی: {e}")




main()

