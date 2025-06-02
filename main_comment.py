#Energy Monitoring and RPM Measurement System Using ESP32 with LCD and TM1637 Display
#Ali Rashidi - t.me/WriteYourWay
import machine  # وارد کردن ماژول machine برای دسترسی به سخت‌افزار
from machine import Pin  # وارد کردن کلاس Pin برای کار با پایه‌های GPIO
import gc  # برای جمع‌آوری زباله‌ها
import time  # برای کار با زمان
import math  # برای توابع ریاضی
from i2c_lcd import I2cLcd  # وارد کردن کتابخانه برای کار با نمایشگر LCD
import tm1637  # وارد کردن کتابخانه برای کار با نمایشگر TM1637

# تنظیمات اولیه LCD و I2C
def setup_lcd():
    try:
        # پیکربندی I2C با استفاده از پایه‌های SCL و SDA
        i2c = machine.SoftI2C(scl=machine.Pin(22), sda=machine.Pin(21), freq=400000)
        devices = i2c.scan()  # اسکن برای پیدا کردن دستگاه‌های متصل به I2C
        if not devices:
            raise Exception("هیچ دستگاهی در باس I2C یافت نشد.")  # اگر دستگاهی پیدا نشد، خطا می‌دهد
        lcd_address = devices[0]  # آدرس اولین دستگاه پیدا شده
        lcd = I2cLcd(i2c, lcd_address, 4, 20)  # ایجاد شیء LCD با 4 خط و 20 ستون
        return lcd  # برگرداندن شیء LCD
    except Exception as e:
        print(f"خطا در تنظیمات LCD: {e}")  # چاپ خطا در صورت بروز مشکل
        return None  # برگرداندن None در صورت بروز خطا

lcd = setup_lcd()  # فراخوانی تابع تنظیم LCD
if not lcd:
    raise SystemExit("برنامه متوقف شد: LCD شناسایی نشد.")  # متوقف کردن برنامه اگر LCD شناسایی نشد

# تنظیمات ADC
try:
    voltage_adc = machine.ADC(machine.Pin(35))  # پیکربندی ADC برای ورودی ولتاژ
    current_adc = machine.ADC(machine.Pin(32))  # پیکربندی ADC برای ورودی جریان
    voltage_adc.width(machine.ADC.WIDTH_12BIT)  # تنظیم دقت ADC به 12 بیت
    voltage_adc.atten(machine.ADC.ATTN_11DB)  # تنظیم Attenuation برای ورودی ولتاژ
    current_adc.width(machine.ADC.WIDTH_12BIT)  # تنظیم دقت ADC برای جریان به 12 بیت
    current_adc.atten(machine.ADC.ATTN_11DB)  # تنظیم Attenuation برای ورودی جریان
except Exception as e:
    print(f"خطا در تنظیمات ADC: {e}")  # چاپ خطا در صورت بروز مشکل
    raise SystemExit("برنامه متوقف شد: خطای ADC.")  # متوقف کردن برنامه در صورت بروز خطا

# ضریب‌های مقیاس تبدیل
PT_SCALE_FACTOR = 0.218  # ضریب تبدیل ولتاژ (ولتاژ واقعی بر حسب ولت)
CT_SCALE_FACTOR = 0.051  # ضریب تبدیل جریان (جریان واقعی بر حسب آمپر)

# تنظیمات نمونه‌برداری
SAMPLE_COUNT = 2000  # تعداد نمونه‌ها
SAMPLE_INTERVAL_US = 100  # فاصله زمانی نمونه‌برداری به میکروثانیه

# آرایه‌های نمونه‌ها
voltage_samples = [0] * SAMPLE_COUNT  # آرایه برای ذخیره نمونه‌های ولتاژ
current_samples = [0] * SAMPLE_COUNT  # آرایه برای ذخیره نمونه‌های جریان

# شناسایی عبور از صفر
def zero_crossing(samples):
    crossings = []  # لیستی برای ذخیره نقاط عبور از صفر
    for i in range(1, len(samples)):
        if samples[i - 1] * samples[i] < 0:  # بررسی عبور از صفر
            crossings.append(i)  # اضافه کردن ایندکس عبور از صفر به لیست
    return crossings  # برگرداندن لیست نقاط عبور از صفر

# محاسبه اختلاف فاز
def calculate_phase_difference(voltage_samples, current_samples):
    try:
        voltage_crossings = zero_crossing(voltage_samples)  # شناسایی نقاط عبور از صفر برای ولتاژ
        current_crossings = zero_crossing(current_samples)  # شناسایی نقاط عبور از صفر برای جریان

        if not voltage_crossings or not current_crossings:
            return 0  # اگر هیچ عبوری شناسایی نشد، اختلاف فاز صفر است

        # محاسبه اختلاف زمان بین اولین عبور از صفر ولتاژ و جریان
        time_diff = (current_crossings[0] - voltage_crossings[0]) * SAMPLE_INTERVAL_US
        phase_difference = (time_diff / (SAMPLE_COUNT * SAMPLE_INTERVAL_US)) * 360  # تبدیل به درجه
        return phase_difference  # برگرداندن اختلاف فاز
    except Exception as e:
        print(f"خطا در محاسبه اختلاف فاز: {e}")  # چاپ خطا در صورت بروز مشکل
        return 0  # برگرداندن صفر در صورت بروز خطا

# محاسبه توان و ضریب توان
def calculate_power():
    try:
        # محاسبه VRMS و IRMS
        vrms = (math.sqrt(sum(v**2 for v in voltage_samples) / SAMPLE_COUNT))  # محاسبه ولتاژ مؤثر
        irms = (math.sqrt(sum(i**2 for i in current_samples) / SAMPLE_COUNT))  # محاسبه جریان مؤثر

        # اختلاف فاز
        phase_difference = calculate_phase_difference(voltage_samples, current_samples)  # محاسبه اختلاف فاز

        # توان واقعی
        real_power = max(0, (sum(v * i for v, i in zip(voltage_samples, current_samples)) / SAMPLE_COUNT))  # محاسبه توان واقعی

        # توان ظاهری
        apparent_power = max(0, ((vrms) * (irms)) + 230)  # محاسبه توان ظاهری
        
        power_factor = min(1.0, max(0, (1 - (real_power / apparent_power if apparent_power else 1.0))))  # محاسبه ضریب توان

        return vrms, irms, real_power, apparent_power, power_factor, phase_difference  # برگرداندن مقادیر محاسبه شده
    except Exception as e:
        print(f"خطا در محاسبه توان: {e}")  # چاپ خطا در صورت بروز مشکل
        return 0, 0, 0, 0, 0, 0  # برگرداندن صفرها در صورت بروز خطا

# مقداردهی اولیه سیستم مانیتورینگ RPM
def initialize_rpm_monitor(clk_pin, dio_pin, hall_pin, timer_interval_ms=100, rpm_multiplier=180, moving_average_window=70):
    """
    مقداردهی اولیه سیستم مانیتورینگ RPM.

    Args:
        clk_pin (int): شماره پایه CLK برای نمایشگر TM1637.
        dio_pin (int): شماره پایه DIO برای نمایشگر TM1637.
        hall_pin (int): شماره پایه اینتراپت سنسور اثر هال.
        timer_interval_ms (int): بازه زمانی تایمر به میلی‌ثانیه (پیش‌فرض: 100ms).
        rpm_multiplier (int): ضریب تبدیل برای RPM (پیش‌فرض: 180).
        moving_average_window (int): طول پنجره میانگین متحرک (پیش‌فرض: 70).
    """
    # پیکربندی نمایشگر TM1637
    tm = tm1637.TM1637(clk=Pin(clk_pin), dio=Pin(dio_pin))  # ایجاد شیء TM1637 با پایه‌های مشخص شده

    # پیکربندی سنسور اثر هال
    hall_sensor_pin = Pin(hall_pin, Pin.IN, Pin.PULL_DOWN)  # تنظیم پایه سنسور اثر هال به عنوان ورودی

    # متغیرها
    hall_interrupt_count = [0]  # استفاده از لیست برای حفظ مقادیر در callback
    rpm_values = [0] * moving_average_window  # آرایه برای ذخیره مقادیر RPM
    rpm_index = [0]  # ایندکس برای دسترسی به آرایه RPM

    def format_number(number, length=4):
        """فرمت شماره برای نمایش روی TM1637"""
        return f'{number:0{length}d}'  # فرمت کردن عدد به طول مشخص

    def display_number(number):
        """نمایش عدد روی نمایشگر TM1637"""
        num_str = format_number(number)  # فرمت کردن عدد
        encoded_digits = [tm.encode_char(char) for char in num_str]  # کدگذاری ارقام برای نمایش
        tm.write(encoded_digits)  # نوشتن ارقام روی نمایشگر

    def calculate_moving_average(new_value):
        """محاسبه میانگین متحرک"""
        nonlocal rpm_index, rpm_values  # دسترسی به متغیرهای غیر محلی
        rpm_values[rpm_index[0]] = new_value  # ذخیره مقدار جدید در آرایه
        rpm_index[0] = (rpm_index[0] + 1) % moving_average_window  # به‌روزرسانی ایندکس
        return sum(rpm_values) // moving_average_window  # محاسبه و برگرداندن میانگین

    def hall_interrupt_handler(pin):
        """افزایش شمارنده اینتراپت سنسور اثر هال"""
        hall_interrupt_count[0] += 1  # افزایش شمارنده در هر بار وقوع اینتراپت

    def timer_callback(timer):
        """محاسبه و نمایش RPM هنگام سرریز تایمر"""
        rpm = hall_interrupt_count[0] * rpm_multiplier  # محاسبه RPM
        hall_interrupt_count[0] = 0  # بازنشانی شمارنده اینتراپت

        # محاسبه میانگین متحرک
        smoothed_rpm = calculate_moving_average(rpm)  # محاسبه میانگین متحرک
        display_number(smoothed_rpm)  # نمایش مقدار میانگین متحرک روی نمایشگر

    # اتصال هندلر اینتراپت به سنسور اثر هال
    hall_sensor_pin.irq(trigger=Pin.IRQ_RISING, handler=hall_interrupt_handler)  # تنظیم اینتراپت برای افزایش شمارنده

    # تنظیم تایمر برای محاسبه RPM
    rpm_timer = machine.Timer(-1)  # ایجاد تایمر
    rpm_timer.init(period=timer_interval_ms, mode=machine.Timer.PERIODIC, callback=timer_callback)  # پیکربندی تایمر

    return rpm_timer, hall_sensor_pin, tm  # برگرداندن تایمر و تنظیمات برای استفاده بیشتر

# حلقه اصلی
def main():
    rpm_timer, hall_sensor, tm_display = initialize_rpm_monitor(16, 17, 33)  # مقداردهی اولیه مانیتورینگ RPM
    while True:  # حلقه بی‌پایان
        try:
            # نمونه‌برداری
            for i in range(SAMPLE_COUNT):
                voltage_samples[i] = (voltage_adc.read()) * PT_SCALE_FACTOR  # خواندن ولتاژ و تبدیل به ولت
                current_samples[i] = (current_adc.read()) * CT_SCALE_FACTOR  # خواندن جریان و تبدیل به آمپر
                time.sleep_us(SAMPLE_INTERVAL_US)  # تاخیر به مدت مشخص

            # محاسبه توان
            vrms, irms, real_power, apparent_power, power_factor, phase_difference = calculate_power()  # محاسبه مقادیر توان

            # نمایش مقادیر
            lcd.clear()  # پاک کردن نمایشگر LCD
            lcd.putstr(f"Vrms: {vrms:.2f}V\nIrms: {irms:.2f}A\nReal_P: {real_power:.0f}W\nPF: {power_factor:.2f}")  # نمایش مقادیر محاسبه شده
            time.sleep(0.5)  # تاخیر برای خواندن مقادیر
            gc.collect()  # جمع‌آوری زباله‌ها (برای آزادسازی حافظه)
        except Exception as e:
            print(f"خطا در حلقه اصلی: {e}")  # چاپ خطا در صورت بروز مشکل

main()  # فراخوانی تابع اصلی برای شروع برنامه


'''

توصیف فنی و کاربرد کد
کد ارائه شده یک سیستم جامع برای نظارت و اندازه‌گیری پارامترهای الکتریکی و سرعت چرخش (RPM) است که برای پلتفرم‌های مبتنی بر میکروکنترلر مانند ESP32 طراحی شده است. عملکردهای اصلی آن شامل موارد زیر است:

1. اندازه‌گیری پارامترهای الکتریکی:
نمونه‌برداری ولتاژ و جریان:

از ورودی‌های ADC (مبدل آنالوگ به دیجیتال) برای نمونه‌برداری مداوم سیگنال‌های ولتاژ و جریان استفاده می‌کند.
مقادیر خام ADC را با استفاده از ضریب‌های کالیبراسیون (PT_SCALE_FACTOR و CT_SCALE_FACTOR) به واحدهای فیزیکی مقیاس می‌کند.
داده‌ها را با فرکانس بالا (SAMPLE_INTERVAL_US) نمونه‌برداری کرده و از اندازه‌های نمونه بزرگ (SAMPLE_COUNT) برای محاسبات دقیق RMS پشتیبانی می‌کند.



محاسبات کلیدی:

VRMS و IRMS: مقادیر ولتاژ و جریان مؤثر را تعیین می‌کند.
پارامترهای توان:
توان واقعی: توان مصرفی واقعی.
توان ظاهری: ترکیبی از توان واقعی و راکتیو.
ضریب توان: اندازه‌گیری کارایی انرژی.
اختلاف فاز: محاسبه تغییر فاز بین ولتاژ و جریان با استفاده از تشخیص عبور از صفر.

کاربرد:

مفید در سیستم‌های نظارت بر انرژی، شبکه‌های هوشمند و تحلیل کیفیت توان برای اندازه‌گیری و گزارش معیارهای الکتریکی حیاتی.
2. نظارت بر RPM:

اندازه‌گیری سرعت چرخش:

از سنسور اثر هال برای تشخیص تعداد دورها استفاده می‌کند.
RPM را با استفاده از یک ضریب قابل تنظیم (rpm_multiplier) و نمونه‌برداری مبتنی بر تایمر (timer_interval_ms) محاسبه می‌کند.
از فیلتر میانگین متحرک (moving_average_window) برای کاهش نویز و خروجی پایدار استفاده می‌کند.




نمایش:

مقدار RPM را بر روی یک نمایشگر 7 قسمتی TM1637 نمایش می‌دهد.

کاربرد:

ضروری برای نظارت بر سرعت موتور، تشخیص عیوب ماشین‌آلات صنعتی و تحلیل عملکرد در سیستم‌های چرخشی.
3. نمایشگر LCD:
با یک LCD مبتنی بر I2C ارتباط برقرار می‌کند تا مقادیر زمان واقعی مانند ولتاژ، جریان و پارامترهای توان را نمایش دهد.
دید کاربرپسند از معیارهای سیستم را فراهم می‌کند.
4. طراحی ماژولار و مقیاس‌پذیر:
مدیریت خطا: مدیریت مناسب استثناها در حین راه‌اندازی سخت‌افزار (مانند LCD و ADC).
توابع قابل استفاده مجدد: سازماندهی شده در توابع واضح برای تنظیم (setup_lcd، initialize_rpm_monitor) و محاسبه (calculate_power، zero_crossing).
قابلیت گسترش: می‌تواند برای شامل کردن سنسورهای اضافی یا اجزای نمایشگر گسترش یابد.





کاربردهای سیستم:
دستگاه‌های نظارت بر انرژی: تحلیل و ثبت مصرف توان در زمان واقعی برای کاربردهای صنعتی و مسکونی.
سیستم‌های هوشمند: ادغام با پلتفرم‌های IoT برای نظارت و کنترل از راه دور.
پروژه‌های آموزشی: نمایش تکنیک‌های پیشرفته در پردازش سیگنال، برنامه‌نویسی میکروکنترلر و ارتباط با سخت‌افزار.
نظارت بر ماشین‌آلات چرخشی: نظارت بر سرعت موتور، تشخیص ناهنجاری‌ها و بهبود کارایی در سیستم‌های مکانیکی.
'''