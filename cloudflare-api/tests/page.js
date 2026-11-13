// Runs the tracker page's own script (../../app.js) in Node against the Worker in src/index.js on the SQLite D1
// stand-in, so a test can press Applied on the page and look at what reached the database. The document below is a
// small stand-in built from index.html (its ids and its form). It is not a browser: layout, CSS and real taps are
// checked by hand in Chromium (README "Tests").
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import api from '../src/index.js';
import {CODE} from './helpers.js';

const ROOT = new URL('../../', import.meta.url);
const html = readFileSync(new URL('index.html', ROOT), 'utf8');
const script = readFileSync(new URL('app.js', ROOT), 'utf8');
const tagOfId = new Map([...html.matchAll(/<(\w+)[^>]*\sid="([^"]+)"/g)].map(match => [match[2], match[1]]));
const formStart = html.indexOf('<form id="record-form">'), form = html.slice(formStart, html.indexOf('</form>', formStart));
const fields = [...form.matchAll(/<(input|select|textarea)\b([^>]*)\bname="(\w+)"([^>]*)>/g)].map(match => {
  const attributes = match[2] + match[4], options = match[1] === 'select' ? [...form.slice(match.index, form.indexOf('</select>', match.index)).matchAll(/<option(?: value="([^"]*)")?>([^<]*)/g)].map(o => o[1] ?? o[2]) : null;
  return {name: match[3], file: /type="file"/.test(attributes), options, initial: options ? options[0] : attributes.match(/\bvalue="([^"]*)"/)?.[1] || ''};
});

// One simple selector: tag, .class, [data-name], or a comma-separated list of those.
function matches(node, selector) {
  return selector.split(',').some(part => {
    const found = part.trim().match(/^(\w+)?((?:\.[\w-]+)*)(?:\[data-([\w-]+)\])?$/);
    if (!found || node.tagName.startsWith('#')) return false;
    const [, tag, classes, data] = found;
    return (!tag || node.tagName === tag.toUpperCase()) && classes.split('.').filter(Boolean).every(name => node.classList.contains(name)) &&
      (!data || data.replace(/-(\w)/g, (_, letter) => letter.toUpperCase()) in node.dataset);
  });
}

class Node {
  constructor(tag, byId) {
    Object.assign(this, {tagName: tag.toUpperCase(), byId, children: [], parent: null, dataset: {}, attributes: {}, listeners: {}, style: {setProperty() {}},
      className: '', value: '', hidden: false, open: false, disabled: false, files: [], text: '', identity: '', offsetWidth: 0, offsetHeight: 0, clientWidth: 0, clientHeight: 0, scrollTop: 0});
    const names = () => String(this.className).split(/\s+/).filter(Boolean), set = list => { this.className = [...new Set(list)].join(' '); };
    this.classList = {contains: name => names().includes(name), add: (...list) => set([...names(), ...list]), remove: (...list) => set(names().filter(name => !list.includes(name))),
      toggle: (name, on = !names().includes(name)) => set(on ? [...names(), name] : names().filter(other => other !== name))};
  }
  get id() { return this.identity; }
  set id(value) { this.identity = value; this.byId.set(value, this); }
  get textContent() { return this.children.length ? this.children.map(child => child.textContent).join('') : this.text; }
  set textContent(value) { this.children = []; this.text = String(value); }
  get firstChild() { return this.children[0] || null; }
  get lastChild() { return this.children.at(-1) || null; }
  get firstElementChild() { return this.children.find(child => !child.tagName.startsWith('#')) || null; }
  get childElementCount() { return this.children.filter(child => !child.tagName.startsWith('#')).length; }
  get isConnected() { return !!this.parent; }
  append(...items) {
    for (const item of items) {
      const nodes = item instanceof Node ? (item.tagName === '#FRAGMENT' ? item.children.splice(0) : [item]) : [Object.assign(new Node('#text', this.byId), {text: String(item)})];
      for (const node of nodes) { node.remove(); node.parent = this; this.children.push(node); }
    }
  }
  replaceChildren(...items) { for (const child of this.children) child.parent = null; this.children = []; this.text = ''; this.append(...items); }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); this.parent = null; }
  after() {}
  setAttribute(name, value) { this.attributes[name] = String(value); if (name === 'class') this.className = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  addEventListener(type, listener) { (this.listeners[type] ||= []).push(listener); }
  querySelectorAll(selector) { return this.children.flatMap(child => [...(matches(child, selector) ? [child] : []), ...child.querySelectorAll(selector)]); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  closest(selector) { return matches(this, selector) ? this : this.parent?.closest(selector) || null; }
  contains(node) { return this.children.some(child => child === node || child.contains(node)); }
  showModal() { this.open = true; }
  close() { this.open = false; }
  focus() {} select() {} click() {} scrollIntoView() {}
  getBoundingClientRect() { return {left: 0, top: 0, right: 0, bottom: 0}; }
}

// Opens the page against `ctx` (from helpers.environment) as a visitor who has typed the right code.
export async function openPage(ctx) {
  const byId = new Map(), calls = [], clipboard = [];
  const document = {visibilityState: 'visible', title: '', documentElement: new Node('html', byId), activeElement: null, addEventListener() {}, execCommand: () => false,
    getElementById(id) { if (!byId.has(id) && tagOfId.has(id)) new Node(tagOfId.get(id), byId).id = id; return byId.get(id) || null; },
    createElement: tag => new Node(tag, byId), createElementNS: (space, tag) => new Node(tag, byId), createDocumentFragment: () => new Node('#fragment', byId),
    querySelectorAll: () => [], querySelector: selector => selector === 'dialog[open]' ? [...byId.values()].find(node => node.tagName === 'DIALOG' && node.open) || null : null};
  const recordForm = document.getElementById('record-form');
  recordForm.elements = Object.fromEntries(fields.map(field => {
    const node = new Node(field.options ? 'select' : 'input', byId);
    if (field.options) Object.defineProperty(node, 'options', {get: () => [...field.options.map(value => ({value})), ...node.children.filter(child => child.tagName === 'OPTION')]});
    return [field.name, Object.assign(node, {value: field.initial, isFile: field.file})];
  }));
  recordForm.reset = () => { for (const field of fields) Object.assign(recordForm.elements[field.name], {value: field.initial, files: []}); };
  recordForm.reportValidity = () => true;
  class FormData { constructor(source) { this.source = source; } *[Symbol.iterator]() { for (const [name, node] of Object.entries(this.source.elements)) if (!node.isFile) yield [name, node.value]; } }
  // The page's requests go straight into the Worker, with the Origin a browser on the published site would send.
  async function fetch(url, options = {}) {
    const body = options.body ?? undefined, bytes = body === undefined ? 0 : typeof body === 'string' ? Buffer.byteLength(body) : body.size;
    const call = {method: options.method || 'GET', path: new URL(url).pathname, bytes};
    calls.push(call);
    ctx.invocation();
    const response = await api.fetch(new Request(url, {method: call.method, body, headers: {Origin: ctx.env.ALLOWED_ORIGIN, ...options.headers, ...(body === undefined ? {} : {'Content-Length': String(bytes)})}}), ctx.env);
    Object.assign(call, {status: response.status, queries: ctx.counters.queries});
    return response;
  }
  const sandbox = {document, fetch, FormData, Node, console, crypto, performance, Intl, URL, Blob, File, TextEncoder, TextDecoder, atob, btoa, structuredClone,
    navigator: {platform: 'MacIntel', userAgent: 'node', clipboard: {writeText: async value => { clipboard.push(value); }}}, matchMedia: () => ({matches: true}),
    setTimeout: () => 0, clearTimeout() {}, setInterval: () => 0, requestAnimationFrame: () => 0, cancelAnimationFrame() {}, ResizeObserver: class { observe() {} },
    localStorage: {getItem: () => null, setItem() {}}, confirm: () => true, scrollTo() {}, addEventListener() {}, TRACKER_API_URL: 'https://tracker.example'};
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(script, sandbox, {filename: 'app.js'});
  const run = code => vm.runInContext(code, sandbox);
  run(`accessCode=${JSON.stringify(CODE)}`);
  await run('load()');
  run('render()');
  const $ = id => document.getElementById(id);
  return {run, calls, clipboard, $, form: recordForm.elements,
    find: (id, selector) => $(id).querySelectorAll(selector),
    tap: (node, extra = {}) => node.onclick({target: node, preventDefault() {}, ...extra}),
    submit: () => recordForm.listeners.submit[0]({preventDefault() {}, currentTarget: recordForm}),
    // The open detail panel as {title, sections: {heading: text}}.
    detail: () => ({open: $('detail').open, title: $('detail-title')?.textContent, sections: Object.fromEntries($('detail-body').querySelectorAll('section').map(section => [section.querySelector('h3').textContent, section.textContent]))})};
}
