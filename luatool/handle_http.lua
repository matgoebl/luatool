-- example handler for http requests via init_wifi_telnethttpd.lua

function http_send_json(c,t)
  c:send("HTTP/1.0 200 OK\r\nContent-type: application/json\r\n\r\n")
  c:send(cjson.encode(t).."\n")
end

-- simple registry for custom handlers by url
if not url_handlers then
 url_handlers={}
end

handle_http = function(c,m,u,p)
 r = nil
 if u == "/info" then
  -- send json demo
  info={info={node.info()},chipid=node.chipid(),flashid=node.flashid(),heap=node.heap()}
  http_send_json(c,info)
 elseif u == "/time" then
  -- send custom header demo
  c:send("HTTP/1.0 200 OK\r\nContent-type: text/plain\r\n\r\n")
  c:send(tmr.time().." "..tmr.now().."\n")
 elseif u == "/led" then
  -- simple set command demo
  if p.set == "1" then
   gpio.mode(ledbutton_pin,gpio.OUTPUT)
   gpio.write(ledbutton_pin,gpio.LOW)
  elseif p.set == "0" then
   gpio.mode(ledbutton_pin,gpio.INPUT,gpio.PULLUP)
  end
  http_send_json(c,{set=p.set})
 else
  -- custom url handler must return table for jsonification or nil for error message
  if url_handlers[u] then
   r = url_handlers[u](c,m,u,p)
  end
  if r then
   http_send_json(c,r)
  else
   c:send("HTTP/1.0 404 ERROR\r\n\r\n")
   c:send(cjson.encode({method=m,path=u,query=p}))
  end
 end
end
