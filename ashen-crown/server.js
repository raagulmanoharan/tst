const http = require('http');
const fs = require('fs');
const path = require('path');

const port = process.env.PORT || 10000;
const file = path.join(__dirname, 'index.html');
const html = fs.readFileSync(file);

http.createServer((req, res) => {
  const url = (req.url || '/').split('?')[0];
  if (url === '/' || url === '/index.html') {
    res.writeHead(200, {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'no-cache',
      'X-Content-Type-Options': 'nosniff',
      'Referrer-Policy': 'strict-origin-when-cross-origin'
    });
    res.end(html);
    return;
  }
  if (url === '/health') {
    res.writeHead(200, {'Content-Type':'text/plain'});
    res.end('ok');
    return;
  }
  res.writeHead(404, {'Content-Type':'text/plain'});
  res.end('Not found');
}).listen(port, '0.0.0.0', () => console.log('Ashen Crown listening on ' + port));
