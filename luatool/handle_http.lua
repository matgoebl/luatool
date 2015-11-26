-- example handler for http requests via init_wifi_telnethttpd.lua

function http_send_json(c,t)
  c:send("HTTP/1.0 200 OK\r\nContent-type: application/json\r\n\r\n")
  c:send(cjson.encode(t).."\n")
end

handle_http = function(c,m,u,p)
 if u == "/info" then
  info={info={node.info()},chipid=node.chipid(),flashid=node.flashid(),heap=node.heap()}
  http_send_json(c,info)
 elseif u == "/time" then
  c:send("HTTP/1.0 200 OK\r\nContent-type: text/plain\r\n\r\n")
  c:send(tmr.time().." "..tmr.now().."\n")
 elseif u == "/led" then
  if p.set == "1" then
   gpio.mode(ledbutton_pin,gpio.OUTPUT)
   gpio.write(ledbutton_pin,gpio.LOW)
  elseif p.set == "0" then
   gpio.mode(ledbutton_pin,gpio.INPUT,gpio.PULLUP)
  end
  http_send_json(c,{set=p.set})
 else
  c:send("HTTP/1.0 404 ERROR\r\n\r\n")
  c:send(cjson.encode({method=m,path=u,query=p}))
 end
end
