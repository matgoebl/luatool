-- ======== init.lua ========
-- Failsafe Start of WiFi and Telnet Service
-- Tested on NodeMCU 0.9.6 build 20150704

-- Circuitry on pin 3 (GPIO0):
--  - Led with 100R to Vcc
--  - Button to GND
-- Press button while power-on to boot into UART downloader mode
ledbutton_pin=3

pcall(function() dofile("config.lua") end)

-- Start telnet service on port 8266
print("start telnetd")
sv=net.createServer(net.TCP, 30)
sv:listen(8266, function(c)
 node.output(function(s) if c~=nil then c:send(s) end end, 0)
 c:on("receive", function(c,d) node.input(d) end)
 c:on("disconnection", function(c) node.output(nil) end)
 -- c:send("Welcome to NodeMCU world.\n> ")
end)

-- Led on for 500ms
gpio.mode(ledbutton_pin,gpio.OUTPUT)
gpio.write(ledbutton_pin,gpio.LOW)
tmr.alarm(0, 500, 0, function()
 -- Press button for standalone ap mode (WIFI AP, DHCP, telnet running, wifi key from config.lua or open)
 gpio.mode(ledbutton_pin,gpio.INPUT,gpio.PULLUP)
 if gpio.read(ledbutton_pin) == gpio.LOW or wifi_cfg == nil then
  print("start ap mode")
  wifi.setmode(wifi.SOFTAP)
  wifi.ap.config({ssid="ESP8266_"..node.chipid(),pwd=wifi_cfg and wifi_cfg.key})
  wifi.ap.setip({ip="192.168.82.1",netmask="255.255.255.0",gateway="192.168.82.1"})
  wifi.ap.dhcp.config({start="192.168.82.100"})
 else
  print("start station mode")
  wifi.setmode(wifi.STATION)
  wifi.sta.config(wifi_cfg.ssid,wifi_cfg.key)
  wifi.sta.connect()
 end
 -- Press button within another 500ms to skip autostart
 tmr.alarm(0, 500, 0, function()
  if gpio.read(ledbutton_pin) ~= gpio.LOW then
   print("start autostart")
   pcall(function() dofile("autostart.lua") end)
  end
 end)
end)
