/* Street Lighting — in-browser engine (Pyodide in a Web Worker).
 * Copyright (C) 2026 Emad Roshandel — GPL-3.0-or-later (see LICENSE)
 *
 * Runs the same Python `streetlight` package as the desktop server, so the
 * GitHub Pages version gives identical results.  Running in a worker keeps
 * the interface responsive during long optimisations.
 */
'use strict';
const PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v0.28.3/full/';
const MODULES = ['__init__.py', 'photometry.py', 'rtables.py', 'geometry.py', 'obstacles.py', 'calc.py',
  'classes.py', 'optimize.py', 'road.py', 'scheme.py', 'electrical.py', 'structural.py', 'energy.py',
  'importers.py', 'contours.py', 'dxf.py', 'api.py'];
let call = null;

async function boot(base) {
  postMessage({ type: 'progress', msg: 'Loading Python…', pct: 10 });
  importScripts(PYODIDE + 'pyodide.js');
  const py = await loadPyodide({ indexURL: PYODIDE });
  postMessage({ type: 'progress', msg: 'Loading numpy…', pct: 45 });
  await py.loadPackage('numpy');
  postMessage({ type: 'progress', msg: 'Loading the lighting engine…', pct: 75 });
  py.FS.mkdirTree('/home/pyodide/streetlight');
  const texts = await Promise.all(MODULES.map(async m => {
    const r = await fetch(base + 'streetlight/' + m);
    if (!r.ok) throw new Error('Missing streetlight/' + m);
    return [m, await r.text()];
  }));
  for (const [n, src] of texts) py.FS.writeFile('/home/pyodide/streetlight/' + n, src);
  await py.runPythonAsync(`
import sys, json
sys.path.insert(0, "/home/pyodide")
import streetlight.api as _api
def _call(path, payload_json):
    try:
        return json.dumps(_api.clean(_api.dispatch(path, json.loads(payload_json or "{}"))), allow_nan=False)
    except KeyError as exc:
        return json.dumps({"error": "Unknown endpoint or missing field: %s" % exc})
    except Exception as exc:
        return json.dumps({"error": str(exc) if isinstance(exc, ValueError) else "%s: %s" % (type(exc).__name__, exc)})
`);
  call = py.globals.get('_call');
  postMessage({ type: 'ready' });
}

onmessage = async (e) => {
  const d = e.data;
  if (d.type === 'boot') {
    try { await boot(d.base); } catch (err) { postMessage({ type: 'fatal', msg: String(err) }); }
    return;
  }
  if (d.type === 'call') {
    let out;
    try { out = call(d.path, d.body); } catch (err) { out = JSON.stringify({ error: String(err) }); }
    postMessage({ type: 'result', id: d.id, out });
  }
};
