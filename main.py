import numpy as np
import traceback 
import re
import time
import flask
import flask_limiter  

from PIL import Image
from io import BytesIO
from flask_caching import Cache
from textwrap import wrap
from flask_limiter.util import get_remote_address

cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})
app = flask.Flask(__name__,
            static_url_path='', 
            static_folder='static/',
            template_folder='static/')
limiter = flask_limiter.Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["1000 per second"]
)
cache.init_app(app)

@app.errorhandler(flask_limiter.errors.RateLimitExceeded)
def handle_ratelimit(e):
  return '<h1 tabindex=2 style="text-align: center; width: auto; height: auto;">Ratelimit exceeded!</h1>', 429
@app.errorhandler(AssertionError)
@limiter.limit('1 per second')
def handle_assertion(e):
  if str(e) == "invalid":
    return flask.render_template('assertions/invalid.html'), 400
  elif str(e) == "incomplete":
    return flask.render_template('assertions/incomplete.html'), 400
  else:
    return flask.render_template('assertions/toobig.html'), 400


@app.errorhandler(Exception)
@limiter.limit('1 per second')
@cache.cached(timeout=50,query_string=True)
def handle_exception(e):
  with open('static/generic-error.html') as f:
    result = f.read()
  return result.replace('{REPLACEME}','<br>'.join(traceback.format_exception(type(e), e, e.__traceback__))), 500

@app.route("/generate/")
@app.route("/generate")
@limiter.limit('16 per minute')
@cache.cached(timeout=50,query_string=True)
def generate():
  ti=time.time()
  q=flask.request.args
  assert all([n in q for n in ['w','h','p','d']]), "incomplete"
  try:
    width = int(q['w'])
    height = int(q['h'])
    scale = float(q['m']) if 'm' in q else 1
    assert all(n > 0 for n in [width,height,scale])
  except:
    raise AssertionError("invalid")
  assert height*width*scale*scale <= 921600, "toobig"
  pal={}
  try:
    if '3h' in q:
        for i,r,g,b,a in wrap(q['p'],5):
          assert not(eval('u'+repr(i)).isnumeric()), "invalid"
          pal[i]=(int(r*2,16),int(g*2,16),int(b*2,16),int(a*2,16))
    else:
        for i,ra,rb,ga,gb,ba,bb,aa,ab in wrap(q['p'],9):
          assert not(eval('u'+repr(i)).isnumeric()), "invalid"
          pal[i]=(int(ra+rb,16),int(ga+gb,16),int(ba+bb,16),int(aa+ab,16))
  except ValueError:
    raise AssertionError("invalid")
  dat = []
  for n in re.split(r'(\d+)',q['d']):
    if eval('u'+repr(n)).isnumeric():
      dat[-1]=dat[-1][:-1]+(dat[-1][-1]*int(n))
    else:
      dat.append(n)
  im=np.zeros((height,width,4),dtype=np.uint8)
  for i,t in enumerate(list(''.join(dat))):
    if i >= (height*width):
      break
    try:
      im[i//width][i%width]=pal[t]
    except:
      raise AssertionError("invalid")
  with BytesIO() as out:
    i=Image.fromarray(im)
    i.resize((int(i.width*scale),int(i.height*scale)),Image.NEAREST).save(out, format='png')
    response = flask.Response(response=out.getvalue(),status=200)
    response.headers.set('Content-Type','image/png')
    return response

@app.route('/')
@limiter.exempt
@cache.cached(timeout=None)
def home():
  return flask.render_template('home.html')

@limiter.exempt
@app.route('/favicon.ico')
def favicon():
  return flask.send_from_directory('static/','favicon.ico', mimetype='image/vnd.microsoft.icon')
