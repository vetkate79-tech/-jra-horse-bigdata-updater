#!/usr/bin/env python3
"""Single canonical pipeline from repair through profiles and validation gates."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path

def call(args,env=None):subprocess.run([sys.executable,*args],check=True,env=env)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--year",type=int,default=2025);ap.add_argument("--pdf-dir",type=Path,required=True)
 ap.add_argument("--workers",type=int,default=2);ap.add_argument("--skip-pdf",action="store_true");a=ap.parse_args()
 html=Path(f"data/race_results_html_{a.year}.csv");repaired=Path(f"data/race_results_repaired_{a.year}.csv")
 if not a.skip_pdf:
  call(["src/run_full_repair_pipeline.py","--pdf-dir",str(a.pdf_dir),"--html",str(html),"--out",str(repaired),
        "--audit",f"status/pdf_repair_{a.year}.json","--workers",str(a.workers)])
 source=repaired if repaired.exists() else html
 env=os.environ.copy();env.update(TARGET_YEAR=str(a.year),PROFILE_SOURCE=str(source),
  PROFILE_OUT=f"data/horse_profiles_repaired_{a.year}.csv",PROFILE_REPORT=f"status/horse_profile_repaired_quality_{a.year}.json")
 hashes=[]
 for _ in range(3):
  call(["src/build_html_horse_profiles.py"],env);hashes.append(digest(Path(env["PROFILE_OUT"])))
 if len(set(hashes))!=1:raise SystemExit("profile generation is not deterministic")
 call(["src/audit_validation_prerequisites.py"])
 call(["src/build_validation_dataset.py"])
 status={"year":a.year,"profile_hashes":hashes,"deterministic":True,"validation_started":Path("data/validation_bets.csv").exists()}
 Path("status/end_to_end_pipeline.json").write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding="utf-8")

if __name__=="__main__":main()
