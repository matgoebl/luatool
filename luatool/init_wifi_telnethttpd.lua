-- ======== init.lua V3.1 for ESP8266 NodeMCU ========
-- Failsafe Start of WiFi and combined Telnet/HTTP Service
-- Also supports NodeMCU 3.0 and adds compatibility
print("init.lua V3.1")

if node.LFS then
 local G=_ENV or getfenv()
 local lf = loadfile
 G.loadfile = function(n)
  if file.exists(n) then return lf(n) end
  local mod = n:match("(.*)%.l[uc]a?$")
  local fn  = mod and node.LFS.get(mod)
  return (fn or error (("Cannot find '%s' in FS or LFS"):format(n))) and fn
 end

 G.dofile = function(n) return assert(loadfile(n))() end
end

-- GPIO0, with button to GND, pull-up high to boot from SPI flash
button_pin=3
button_on=gpio.LOW

-- GPIO2, with LED to Vss (default on ESP-12F modules), pull-up high to boot from SPI flash
led_pin=4
led_on=gpio.LOW

-- compatibility for older api
if not cjson then cjson = sjson end

if not tmr.alarm then
 local new_tmr={}
 for k,v in pairs(tmr) do
  new_tmr[k] = v
 end
 tmr=new_tmr
 tmrs={}
 tmr.alarm = function(id,interval_ms,mode,cb)
  tmrs[id]=tmr.create()
  tmrs[id]:alarm(interval_ms,mode,cb)
 end
 tmr.stop = function(id)
  if tmrs[id] then
   if tmrs[id]:stop() then tmrs[id]:unregister() end
   tmrs[id] = nil
  end
 end
end


dummy,bootreason=node.bootreason()

cfg={}
pcall(function() dofile("config.lc") end)
pcall(function() dofile("config.lua") end)
pcall(function() pcall(loadstring(cfg.init)) end)  cfg.init=nil

if bootreason == 5 then
 pcall(function() dofile("awake.lc") end)
end

local srv
if pipe then
 srv=function()
  sv=net.createServer(net.TCP, 30)
  sv:listen(8266, function(c)
   sv_conn=c
   local sv_out=nil
   local sv_telnet=false
   local function sv_send(c) if sv_out then local s=sv_out:read(1400)
    if s and #s>0 then c:send(s) end end end
   c:on("sent", sv_send)
   c:on("disconnection", function(c) node.output(nil) sv_out=nil
    collectgarbage() end)
   node.output(function(p) if c and sv_telnet then sv_out=p sv_send(c) end return false end, 1)
   c:on("receive", function(c,d)
    collectgarbage()
    if cfg.auth and sv_telnet == false and d:find(cfg.auth,1,true) == nil then
     c:close()
     return
    end
    if handle_http ~= nil and sv_telnet == false and d ~= nil then
     local m,u,q=d:match("^([^ ]*)[ ]+([^? ]*)\??([^ ]*)[ ]+[Hh][Tt][Tt][Pp]/")
     if m ~= nil and u ~= nil then
      d=nil
      c:on("receive",function() end)
      local r=handle_http(c,m,u,q)
      if r~=true then c:close() end
      return
     end
    end
    sv_telnet = true
    node.input(d)
    c:on("receive", function(c,d) node.input(d) end)
   end)
  end)
 end
else
 srv=function()
  sv=net.createServer(net.TCP, 30)
  sv:listen(8266, function(c)
   sv_telnet=false
   sv_conn=c
   c:on("sent",function() end)
   c:on("disconnection", function(c) node.output(nil) end)
   c:on("receive", function(c,d)
    collectgarbage()
    if cfg.auth and sv_telnet == false and d:find(cfg.auth,1,true) == nil then
     c:close()
     return
    end
    if handle_http ~= nil and sv_telnet == false and d ~= nil then
     local m,u,q=d:match("^([^ ]*)[ ]+([^? ]*)\??([^ ]*)[ ]+[Hh][Tt][Tt][Pp]/")
     if m ~= nil and u ~= nil then
      d=nil
      c:on("receive",function() end)
      local r=handle_http(c,m,u,q)
      if r~=true then c:close() end
      return
     end
    end
    sv_telnet = true
    node.output(function(s) if c~=nil then c:send(s) end end, 0)
    node.input(d)
   end)
  end)
 end
end

-- Start telnet/http service on port 8266
print("start telnet/httpd")
srv()

-- Switch LED on and wait for 100ms
gpio.mode(led_pin,gpio.OUTPUT)
gpio.write(led_pin,led_on)

gpio.mode(button_pin,gpio.INPUT,button_on==gpio.LOW and gpio.PULLUP or gpio.FLOAT)

-- Press button shortly after power-on for failsafe mode (WIFI AP, DHCP, telnet running, wifi key from config.lua or default)
-- If you hold the button while power-on it boots into UART downloader mode
tmr.alarm(0, tonumber(cfg.failsafe_wait) or 1000, 0, function()

 if gpio.read(button_pin) ~= button_on then

  print("start station mode")
  gpio.write(led_pin,led_on==gpio.LOW and gpio.HIGH or gpio.LOW)

  wifi.setmode(wifi.STATION)
  if cfg.ssid and cfg.key then
   if wifi.sta.getdefaultconfig then
    -- new api
    wifi.sta.config({ssid=cfg.ssid,pwd=cfg.key})
   else
    wifi.sta.config(cfg.ssid,cfg.key)
   end
  end
  wifi.sta.connect()

  tmr.alarm(0, ((bootreason == 1 or bootreason == 2 or bootreason == 3) and 30000) or
               ((bootreason == 0 or bootreason == 6) and tonumber(cfg.powerup_wait)) or
               tonumber(cfg.autostart_wait) or 1, 0, function()
    print("start autostart")
    pcall(function() dofile("autostart.lua") end)
  end)

 else

  print("start failsafe ap mode")
  pwm.setup(led_pin, 5, 900)
  pwm.start(led_pin)
  failsafe=true

  cfg.auth=nil

  wifi.setmode(wifi.STATIONAP)
  wifi.ap.config({ssid="ESP8266_"..node.chipid(),pwd="NodeMCU!"})
  wifi.ap.setip({ip="192.168.82.1",netmask="255.255.255.0",gateway="192.168.82.1"})
  wifi.ap.dhcp.config({start="192.168.82.100"})

  if enduser_setup then
   enduser_setup.manual(true)
   enduser_setup.start()
  end

 end
end)
