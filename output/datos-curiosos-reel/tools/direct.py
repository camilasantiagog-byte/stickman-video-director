import hashlib, urllib.request, urllib.parse, urllib.error, time, sys, os
UA={"User-Agent":"DatosCuriososReelBot/1.0 (educational short video generator)"}
C={
"octopus":["Octopus_(28836592458).jpg","Pulpo_común_(Octopus_vulgaris),_Parque_natural_de_la_Arrábida,_Portugal,_2020-07-31,_DD_111.jpg","Pulpo_común_(Octopus_vulgaris),_Cathedral_Cave,_Gozo,_Malta,_2021-08-23,_DD_28.jpg"],
"honey":["Runny_hunny.jpg","Honey_comb.jpg","Honeycomb.jpg","Honey.jpg"],
"egypt":["Kheops-Pyramid.jpg","All_Gizah_Pyramids.jpg","Great_Sphinx_of_Giza_-_20080716a.jpg"],
"venus":["Venus-real_color.jpg","Venus_globe.jpg","Venus_from_Mariner_10.jpg","PIA23791-Venus-NewlyProcessedView-20200608.jpg"],
"flamingo":["Flamingos_Laguna_Colorada.jpg","Phoenicopterus_ruber_in_São_Paulo_Zoo.jpg","Lesser_Flamingos_at_Lake_Nakuru.jpg","Greater_flamingos.jpg","Flamingo_chick.jpg"],
"eiffel":["Tour_Eiffel_Wikimedia_Commons.jpg","Tour_Eiffel_Wikimedia_Commons_(cropped).jpg","Paris_-_Eiffelturm_und_Marsfeld2.jpg","Eiffel_Tower_from_the_Tour_Montparnasse_3,_Paris_May_2014.jpg","Tour_eiffel_at_sunrise_from_the_trocadero.jpg"],
"cow":["Cow_female_black_white.jpg","Cows_in_green_field.jpg","Cattle_in_field.jpg","Cows_grazing.jpg","Cow_(Fleckvieh_breed)_Oeschinensee_Slaunger_2009-07-07.jpg"],
"brain":["Human_brain_NIH.png","MRI_head_side.jpg","Skull_and_brain_normal_human.svg","Brain_Anatomy.jpg","Human_brain.jpg","Neurons_in_the_brain.jpg","GFPneuron.png","Pyramidal_hippocampal_neuron_40x.jpg"],
}
out="img"
def url_for(name, thumb=True):
    h=hashlib.md5(name.encode()).hexdigest(); q=urllib.parse.quote(name)
    base=f"https://upload.wikimedia.org/wikipedia/commons/"
    return f"{base}thumb/{h[0]}/{h[:2]}/{q}/1280px-{q}" if thumb else f"{base}{h[0]}/{h[:2]}/{q}"
def get(u):
    for i in range(4):
        try: return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code==429: time.sleep(10*(i+1)); continue
            return None
for k,names in [(k,v) for k,v in C.items() if k in sys.argv[1:]]:
    n=0
    for name in names:
        if n>=int(os.environ.get("NMAX","2")): break
        for thumb in (True,False):
            d=get(url_for(name,thumb)); time.sleep(1.5)
            if d and len(d)>20000:
                ext=".png" if name.lower().endswith(".png") else ".jpg"
                open(f"{out}/{k}_{n}{ext}","wb").write(d); print("OK",k,n,name,"thumb" if thumb else "orig",flush=True); n+=1; break
        else: print("miss",name,flush=True)
