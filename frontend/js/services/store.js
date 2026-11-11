/** Shared app metadata cache (user, subjects, AI status, demo counts). */

import { api } from "../api.js";

let meta = null;
let metaPromise = null;

export async function loadMeta({ force = false } = {}) {
  if (force) {
    meta = null;
    metaPromise = null;
  }
  if (meta) return meta;
  if (metaPromise) return metaPromise;
  metaPromise = api
    .get("/meta")
    .then((response) => {
      meta = response.data;
      window.dispatchEvent(new CustomEvent("studyflow:meta", { detail: meta }));
      return meta;
    })
    .catch((error) => {
      metaPromise = null;
      throw error;
    });
  return metaPromise;
}

export function getMeta() {
  return meta;
}

export function getUser() {
  return meta ? meta.user : null;
}

export function getSubjects() {
  return meta && Array.isArray(meta.subjects)
    ? meta.subjects
    : ["语文", "数学", "英语", "物理", "化学", "生物", "政治", "历史", "地理", "综合"];
}

export function getAIStatus() {
  return meta ? meta.ai : null;
}

export function updateMetaFromSettings(partial) {
  if (!meta) return;
  if (partial.user) meta.user = partial.user;
  if (partial.ai) meta.ai = partial.ai;
  if (partial.demo) meta.demo = partial.demo;
  window.dispatchEvent(new CustomEvent("studyflow:meta", { detail: meta }));
}
