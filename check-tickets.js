const https = require('https');

const PROD_ID = process.env.PROD_ID || '211992';
const SLACK_WEBHOOK = process.env.SLACK_WEBHOOK;

// TK Global API endpoint (需要實際抓取)
const checkTickets = () => {
  const options = {
    hostname: 'tkglobal.melon.com',
    path: `/api/performance/seat?prodId=${PROD_ID}&langCd=EN`,
    method: 'GET',
    headers: {
      'User-Agent': 'Mozilla/5.0',
      'Accept': 'application/json',
      'Referer': `https://tkglobal.melon.com/performance/index.htm?langCd=EN&prodId=${PROD_ID}`
    }
  };

  const req = https.request(options, (res) => {
    let data = '';
    
    res.on('data', (chunk) => {
      data += chunk;
    });
    
    res.on('end', () => {
      console.log('Status:', res.statusCode);
      console.log('Response:', data);
      
      // 檢查是否有票
      // 根據實際 API 回應調整
      if (data.includes('available') || data.includes('可用')) {
        sendSlackNotification('🎫 TWICE票來了！快搶！');
      }
    });
  });

  req.on('error', (e) => {
    console.error('Error:', e.message);
  });

  req.end();
};

const sendSlackNotification = (message) => {
  if (!SLACK_WEBHOOK) return;
  
  const postData = JSON.stringify({
    text: message,
    link_names: 1
  });

  const url = new URL(SLACK_WEBHOOK);
  const options = {
    hostname: url.hostname,
    path: url.pathname,
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(postData)
    }
  };

  const req = https.request(options, (res) => {
    console.log('Slack notification sent:', res.statusCode);
  });

  req.write(postData);
  req.end();
};

checkTickets();
