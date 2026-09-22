import subprocess, json, re, select, time, sys
p = subprocess.Popen(["/global/tools/freeware/verible/v0.0-4080/bin/verible-verilog-ls"],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
def send(obj):
    body = json.dumps(obj)
    p.stdin.write(f"Content-Length: {len(body)}\r\n\r\n{body}"); p.stdin.flush()
def read(timeout=45):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r, _, _ = select.select([p.stdout], [], [], 0.5)
        if not r: continue
        line = p.stdout.readline()
        if not line.startswith("Content-Length:"): continue
        n = int(line.split(":")[1]); p.stdout.readline()
        return json.loads(p.stdout.read(n))
    return {"timeout": True}
send({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"processId":1,"rootUri":"file:///nfs/workspace32/lwang/XIN","capabilities":{}}})
read()
send({"jsonrpc":"2.0","method":"initialized","params":{}})
f = "/nfs/workspace32/lwang/XIN/hw/rtl/eic/eic.sv"
text = open(f).read()
send({"jsonrpc":"2.0","method":"textDocument/didOpen","params":{"textDocument":{"uri":"file://"+f,"languageId":"verilog","version":1,"text":text}}})
t0 = time.time()
send({"jsonrpc":"2.0","id":2,"method":"textDocument/hover","params":{"textDocument":{"uri":"file://"+f},"position":{"line":19,"character":7}}})
while True:
    r = read()
    if r.get("timeout"):
        print(f"TIMEOUT after {time.time()-t0:.0f}s, proc alive: {p.poll() is None}"); break
    if "id" in r:
        print(f"hover ({time.time()-t0:.1f}s):", str(r.get('result'))[:120]); break
print("poll:", p.poll())
time.sleep(1)
err = ""
try:
    p.stderr.close() if False else None
    p.kill()
except Exception: pass
