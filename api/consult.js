const SITE_BASE = 'https://vetkate79-tech.github.io/-jra-horse-bigdata-updater';
let horseCache = null;
let horseCacheAt = 0;

async function loadHorses() {
  if (horseCache && Date.now() - horseCacheAt < 300000) return horseCache;
  const r = await fetch(SITE_BASE + '/data/horses/base_catalog.json', { cache: 'no-store' });
  if (!r.ok) return [];
  const d = await r.json();
  horseCache = Array.isArray(d.horses) ? d.horses : [];
  horseCacheAt = Date.now();
  return horseCache;
}

function matchedHorses(question, horses) {
  const q = String(question || '').normalize('NFKC');
  const rows = [];
  for (const h of horses) {
    const name = String(h.horse_name || '');
    if (name && q.includes(name)) {
      rows.push({
        horse_name: h.horse_name,
        sex_age: h.sex_age,
        trainer: h.trainer,
        sire: h.sire,
        damsire: h.damsire,
        current_class: h.current_class_label || h.current_class,
        active: h.active,
        latest_race_date: h.latest_race_date,
        latest_finish: h.latest_finish,
        running_style: h.running_style_label,
        running_style_provisional: h.running_style_provisional === true
      });
      if (rows.length >= 5) break;
    }
  }
  return rows;
}

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', 'https://vetkate79-tech.github.io');
  res.setHeader('Access-Control-Allow-Methods', 'POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Cache-Control', 'no-store');
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'METHOD_NOT_ALLOWED' });

  const question = String(req.body && req.body.question || '').trim();
  if (!question) return res.status(400).json({ error: 'QUESTION_REQUIRED' });
  if (question.length > 1200) return res.status(400).json({ error: 'QUESTION_TOO_LONG' });
  if (!process.env.OPENAI_API_KEY) return res.status(503).json({ error: 'AI_NOT_CONFIGURED' });

  try {
    const horses = await loadHorses().catch(() => []);
    const matches = matchedHorses(question, horses);
    const context = req.body && req.body.context && typeof req.body.context === 'object' ? req.body.context : {};
    const userContent = [
      '質問:',
      question,
      '',
      'サイト内で一致した馬データ:',
      JSON.stringify(matches, null, 2),
      '',
      '画面コンテキスト:',
      JSON.stringify(context, null, 2)
    ].join('\n');

    const r = await fetch('https://api.openai.com/v1/responses', {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer ' + process.env.OPENAI_API_KEY,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: process.env.OPENAI_MODEL || 'gpt-5.6-luna',
        input: [
          {
            role: 'system',
            content: 'あなたはJRA競馬サイトの相談AIです。日本語で初心者にも分かりやすく答えてください。最初に質問へ直接答えてください。サイト内馬データにある事実は使ってよいですが、そこにない馬固有情報、最新出走、オッズ、人気、確率、調教、結果を推測しないでください。脚質が暫定なら暫定と明示してください。人気やオッズは純粋能力評価へ混ぜないでください。データ不足なら確認できないと明示し、馬データ、レース選択、詳細分析のどこを確認すべきか案内してください。一般的な競馬用語や仕組みは通常の知識で説明して構いません。'
          },
          { role: 'user', content: userContent }
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

    return res.status(200).json({
      title: matches.length ? matches[0].horse_name + 'について' : 'AIからの回答',
      answer: text,
      grounded_horses: matches.map(x => x.horse_name),
      terms_used: []
    });
  } catch (e) {
    return res.status(500).json({ error: 'AI_INTERNAL_ERROR' });
  }
};
