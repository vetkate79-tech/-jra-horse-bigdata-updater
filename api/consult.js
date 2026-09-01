module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', 'https://vetkate79-tech.github.io');
  res.setHeader('Access-Control-Allow-Methods', 'POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Cache-Control', 'no-store');
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'METHOD_NOT_ALLOWED' });
  const question = String(req.body && req.body.question || '').trim();
  if (!question) return res.status(400).json({ error: 'QUESTION_REQUIRED' });
  if (!process.env.OPENAI_API_KEY) return res.status(503).json({ error: 'AI_NOT_CONFIGURED' });
  try {
    const r = await fetch('https://api.openai.com/v1/responses', {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer ' + process.env.OPENAI_API_KEY,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: process.env.OPENAI_MODEL || 'gpt-5.6-luna',
        input: [
          { role: 'system', content: 'あなたはJRA競馬サイトの相談AIです。日本語で簡潔に答えてください。馬固有の最新情報、オッズ、人気、確率、調教、結果など確認できない事実は推測しないでください。データ不足なら確認できないと明示してください。' },
          { role: 'user', content: question }
        ],
        max_output_tokens: 700
      })
    });
    const data = await r.json();
    if (!r.ok) return res.status(502).json({ error: 'AI_UPSTREAM_ERROR' });
    let text = data.output_text || '';
    if (!text && Array.isArray(data.output)) {
      text = data.output.flatMap(x => x.content || []).filter(x => x.type === 'output_text').map(x => x.text || '').join('\n');
    }
    if (!text) return res.status(502).json({ error: 'AI_EMPTY_RESPONSE' });
    return res.status(200).json({ title: 'AIからの回答', answer: text, terms_used: [] });
  } catch (e) {
    return res.status(500).json({ error: 'AI_INTERNAL_ERROR' });
  }
};
