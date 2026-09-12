"""Both tape regions take newest pixels without replaying old queued frames."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from muslimsim.devices import toliss_sd_image as sd
from test_toliss_sd_image import Canvas

def check():
    c=Canvas()
    blank=(bytes(448*3),)*448
    def draw(rows,seq):
        sd.draw(c,'bleed',((seq,1000+seq),1,rows,10),latest=True)
    draw(blank,2)
    def changed(value):
        rows=list(blank)
        for y in range(0,120,2):
            row=bytearray(rows[y])
            for x in (10,30,50,70,90,110,320,340,360,380,400,420):
                row[x*3:x*3+3]=bytes((value,255-value,10))
            rows[y]=bytes(row)
        return tuple(rows)
    old=changed(80);new=changed(170)
    draw(old,4)
    assert c._toliss_sd_pixels['pending'] is not None
    assert c.rows()==c._toliss_sd_pixels['rows']
    draw(new,6)
    assert c._toliss_sd_pixels['target_key'][0]==6
    assert c.rows()==c._toliss_sd_pixels['rows']
    assert bytes((170,85,10)) in c.rows()[0][:448*3//3]
    assert bytes((170,85,10)) in c.rows()[0][448*3*2//3:]
    for _ in range(30):
        draw(new,6)
        if c._toliss_sd_pixels['pending'] is None:break
    assert c.rows()==new
    # Erase while another delta is unfinished; no old pixels may survive.
    draw(old,8)
    for _ in range(30):
        draw(blank,10)
        if c._toliss_sd_pixels['pending'] is None:break
    assert c.rows()==blank
    reports=c.total_reports
    draw(blank,12)
    assert c.total_reports==reports
    print('  [ok] PFD newest-frame replacement, both tape bands, committed shadow, erasure and idle')

if __name__=='__main__':check()
