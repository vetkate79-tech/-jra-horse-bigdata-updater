#!/usr/bin/env python3
"""Hybrid JRA PDF extractor: embedded text for names, OCR for custom-font numbers.
Output is quarantined unless every race passes row-count and numeric checks.
"""
import csv, json, os, re, subprocess, tempfile
from pathlib import Path

DPI=400
NAME_ROW=re.compile(r"^\s*(.{2,100}?)\s+(牡|牝|騸)\s+(?:黒鹿|青鹿|栃栗|栗|鹿|芦|青|白)(?:\s|$)")
KATA=re.compile(r"^[ァ-ヶー・ヴヷヸヹヺ]{2,18}$")
TIME=re.compile(r"\b([0-3])\s*[:：]\s*([0-5]\d)\s*[.．]\s*(\d)\b")
ODDS=re.compile(r"(?<!\d)(\d{1,3})\s*[.．]\s*(\d)(?!\d)")
VENUES={"sapporo":"札幌","hakodate":"函館","fukushima":"福島","niigata":"新潟",
"tokyo":"東京","nakayama":"中山","chukyo":"中京","kyoto":"京都","hanshin":"阪神","kokura":"小倉"}

def run(*args):
 return subprocess.run(args,check=True,capture_output=True,text=True).stdout

def clean_name(raw):
 parts=[x for x in re.split(r"\s{2,}",raw.strip()) if x]
 name=re.sub(r"\s+","",parts[-1] if parts else raw)
 name=re.sub(r"^[!#%&()*+,.0-9:;<>?@A-Z\[\]^_\x60a-z{|}~（）〔〕・]+","",name)
 return name if KATA.fullmatch(name) else None

def embedded_names(pdf,page,side):
 x=0 if side==0 else 421
 text=run("pdftotext","-f",str(page),"-l",str(page),"-layout","-x",str(x),"-y","0","-W","421","-H","595",str(pdf),"-")
 names=[]
 for line in text.splitlines():
  m=NAME_ROW.search(line)
  if m:
   name=clean_name(m.group(1))
   if name and name not in names:names.append(name)
 return names,text

def ocr_words(image):
 tsv=run("tesseract",str(image),"stdout","-l","jpn+eng","--psm","11","tsv")
 rows=list(csv.DictReader(tsv.splitlines(),delimiter="\t"));out=[]
 for r in rows:
  text=r.get("text","").strip()
  try:conf=float(r.get("conf","-1"))
  except ValueError:conf=-1
  if text and conf>=15:
   out.append({"text":text,"x":int(r["left"]),"y":int(r["top"]),"w":int(r["width"]),"h":int(r["height"]),"conf":conf})
 return out

def numeric_rows(words,width):
 # OCR often splits 1:55.9 into several tokens. Reconstruct visual rows by y-coordinate.
 bands=[]
 for word in sorted(words,key=lambda w:(w["y"]+w["h"]/2,w["x"])):
  cy=word["y"]+word["h"]/2
  best=None
  for band in bands:
   if abs(cy-band["y"])<=24:
    best=band;break
  if best is None:
   best={"y":cy,"words":[]};bands.append(best)
  best["words"].append(word)
  best["y"]=sum(x["y"]+x["h"]/2 for x in best["words"])/len(best["words"])
 out=[]
 for band in sorted(bands,key=lambda b:b["y"]):
  parts=sorted(band["words"],key=lambda w:w["x"])
  compact="".join(w["text"] for w in parts).replace(" ","")
  match=TIME.search(compact)
  if not match:continue
  time_value=f"{match.group(1)}:{match.group(2)}.{match.group(3)}"
  left=[w["text"] for w in parts if w["x"]<width*.12]
  nums=[int(x) for x in re.findall(r"\d{1,2}"," ".join(left))]
  horse_no=nums[-1] if nums else None
  body_candidates=[]
  for w in parts:
   if width*.55<w["x"]<width*.72:
    body_candidates += [int(x) for x in re.findall(r"(?<!\d)([34-6]\d{2})(?!\d)",w["text"])]
  odds_candidates=[]
  for w in parts:
   if w["x"]>width*.78:
    for m in ODDS.finditer(w["text"]):odds_candidates.append(float(m.group(1)+"."+m.group(2)))
  out.append({"horse_no":horse_no,"time":time_value,"body_weight":body_candidates[-1] if body_candidates else None,
              "win_odds":odds_candidates[-1] if odds_candidates else None,
              "ocr_confidence":round(sum(w["conf"] for w in parts)/len(parts),2),
              "ocr_line":" ".join(w["text"] for w in parts)})
 return out

def filename_meta(pdf):
 m=re.search(r"(\d{4})-(\d+)([a-z]+)(\d+)\.pdf$",pdf.name,re.I)
 if not m:return {}
 return {"year":int(m.group(1)),"meeting_no":int(m.group(2)),"course":VENUES.get(m.group(3).lower(),m.group(3)),
         "meeting_day":int(m.group(4))}

def pdf_date(pdf):
 info=run("pdfinfo",str(pdf))
 m=re.search(r"CreationDate:\s+\w{3}\s+(\w{3})\s+(\d{1,2}).*?(\d{4})",info)
 if not m:return ""
 months={x:i+1 for i,x in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
 return f"{m.group(3)}-{months[m.group(1)]:02d}-{int(m.group(2)):02d}"

def extract(pdf):
 meta=filename_meta(pdf);race_date=pdf_date(pdf)
 pages=int(re.search(r"Pages:\s+(\d+)",run("pdfinfo",str(pdf))).group(1))
 accepted=[];quarantine=[];audit=[]
 with tempfile.TemporaryDirectory() as td:
  root=Path(td)
  for page in range(1,pages+1):
   base=root/f"p{page}"
   subprocess.run(["pdftoppm","-f",str(page),"-l",str(page),"-singlefile","-r",str(DPI),"-png",str(pdf),str(base)],check=True,capture_output=True)
   from PIL import Image
   image=Image.open(base.with_suffix(".png"));half=image.width//2
   for side in (0,1):
    race_no=(page-1)*2+side+1
    if race_no>12:continue
    crop=image.crop((side*half,0,(side+1)*half,image.height));crop_path=root/f"p{page}s{side}.png";crop.save(crop_path)
    names,embedded=embedded_names(pdf,page,side);numbers=numeric_rows(ocr_words(crop_path),half)
    reasons=[]
    if not 3<=len(names)<=18:reasons.append(f"name_count={len(names)}")
    if len(numbers)!=len(names):reasons.append(f"row_mismatch names={len(names)} numeric={len(numbers)}")
    if any(x["horse_no"] is None or x["body_weight"] is None or x["win_odds"] is None for x in numbers):reasons.append("missing_core_numeric")
    if len({x["horse_no"] for x in numbers})!=len(numbers):reasons.append("duplicate_horse_no")
    audit.append({"race_no":race_no,"names":len(names),"numeric_rows":len(numbers),"reasons":reasons})
    target=quarantine if reasons else accepted
    for pos,(name,num) in enumerate(zip(names,numbers),1):
     target.append({**meta,"race_date":race_date,"race_no":race_no,"finish_position":pos,"horse_name":name,**num,
                    "validation_status":"QUARANTINED" if reasons else "PASS","validation_reason":";".join(reasons)})
 return accepted,quarantine,audit

def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument("pdf",type=Path);p.add_argument("--out",type=Path,default=Path("data/ocr_extracted.csv"));args=p.parse_args()
 accepted,quarantine,audit=extract(args.pdf)
 args.out.parent.mkdir(parents=True,exist_ok=True)
 fields=list((accepted or quarantine)[0]) if accepted or quarantine else []
 with args.out.open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(accepted)
 q=args.out.with_name(args.out.stem+"_quarantine.csv")
 with q.open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(quarantine)
 audit_path=args.out.with_suffix(".audit.json");audit_path.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({"accepted":len(accepted),"quarantined":len(quarantine),"audit":audit},ensure_ascii=False))

if __name__=="__main__":main()
