const http = require("http");
const fs = require("fs");
const path = require("path");
const types = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript" };
http
  .createServer((req, res) => {
    let p = decodeURIComponent(req.url.split("?")[0]);
    if (p === "/") p = "/index.html";
    const fp = path.join(__dirname, p);
    fs.readFile(fp, (err, data) => {
      if (err) { res.writeHead(404); res.end("not found"); return; }
      res.writeHead(200, { "Content-Type": types[path.extname(fp)] || "text/plain" });
      res.end(data);
    });
  })
  .listen(8099, () => console.log("listening on 8099"));
