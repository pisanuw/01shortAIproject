// ── Constants ──────────────────────────────────────────────────────────────────

const QUARTER_ORDER = ["Autumn", "Winter", "Spring", "Summer"];
const TERM_TO_QUARTER = { AUT: "Autumn", WIN: "Winter", SPR: "Spring", SUM: "Summer" };
const PAGE_SIZE = 20;
const FILTER_DROPDOWN_THRESHOLD = 5;
const DATA_VERSION = Date.now();

function withDataVersion(url) {
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}v=${DATA_VERSION}`;
}

// ── FilterDropdown component ───────────────────────────────────────────────────

class FilterDropdown {
  constructor(containerId, onChange) {
    this._value = "";
    this._onChange = onChange;
    this._options = [];
    this._allLabel = "";
    this._open = false;

    this._container = document.getElementById(containerId);
    this._container.innerHTML = `
      <button type="button" class="filter-dropdown-btn" aria-haspopup="listbox" aria-expanded="false">
        <span class="filter-dropdown-value"></span>
        <span class="filter-dropdown-arrow">&#9662;</span>
      </button>
      <div class="filter-dropdown-panel" hidden>
        <input type="text" class="filter-dropdown-search" placeholder="Filter…" autocomplete="off" />
        <ul class="filter-dropdown-list" role="listbox"></ul>
      </div>
    `;

    this._btn       = this._container.querySelector(".filter-dropdown-btn");
    this._panel     = this._container.querySelector(".filter-dropdown-panel");
    this._search    = this._container.querySelector(".filter-dropdown-search");
    this._list      = this._container.querySelector(".filter-dropdown-list");
    this._valueSpan = this._container.querySelector(".filter-dropdown-value");

    this._btn.addEventListener("click", e => { e.stopPropagation(); this._toggle(); });
    this._search.addEventListener("input", () => this._renderList(this._search.value));
    document.addEventListener("click", e => { if (!this._container.contains(e.target)) this._close(); });
    document.addEventListener("keydown", e => { if (e.key === "Escape") this._close(); });
  }

  populate(values, allLabel, labelsByValue = {}) {
    const prev = this._value;
    this._allLabel = allLabel;
    this._options = [
      { value: "", label: allLabel },
      ...values.map(v => ({ value: v, label: labelsByValue[v] || v }))
    ];
    if (prev && !values.includes(prev)) this._value = "";
    const showSearch = values.length > FILTER_DROPDOWN_THRESHOLD;
    this._search.hidden = !showSearch;
    this._search.value = "";
    this._renderList("");
    this._updateBtn();
  }

  get value() { return this._value; }
  set value(v) { this._value = v; this._updateBtn(); }

  focus() { this._btn.focus(); }

  _renderList(query) {
    const q = query.trim().toLowerCase();
    const filtered = q
      ? this._options.filter(o => o.value === "" || o.label.toLowerCase().includes(q))
      : this._options;
    this._list.innerHTML = filtered.map(o =>
      `<li role="option" data-value="${o.value}" class="${o.value === this._value ? "selected" : ""}">${o.label}</li>`
    ).join("");
    this._list.querySelectorAll("li").forEach(li => {
      li.addEventListener("click", () => {
        this._value = li.dataset.value;
        this._close();
        this._updateBtn();
        this._onChange();
      });
    });
  }

  _updateBtn() {
    const opt = this._options.find(o => o.value === this._value);
    this._valueSpan.textContent = opt ? opt.label : this._allLabel;
    this._btn.classList.toggle("active-filter", !!this._value);
  }

  _toggle() { this._open ? this._close() : this._openPanel(); }

  _openPanel() {
    this._open = true;
    this._panel.hidden = false;
    this._btn.setAttribute("aria-expanded", "true");
    this._btn.classList.add("open");
    this._search.value = "";
    this._renderList("");
    if (!this._search.hidden) this._search.focus();
    else this._list.querySelector("li")?.focus();
  }

  _close() {
    this._open = false;
    this._panel.hidden = true;
    this._btn.setAttribute("aria-expanded", "false");
    this._btn.classList.remove("open");
  }
}

// ── State ──────────────────────────────────────────────────────────────────────

let state = {
  view: "campus",       // "campus" | "dept" | "filter" | "professor"
  campus: null,         // "B" | "T" | "S"
  dept: null,           // dept code string e.g. "css"
  catalogIndex: null,   // parsed catalog_index.json
  professorIndex: null, // parsed professor_index.json
  courseIndex: null,    // parsed course_index.json
  evalIndex: null,      // parsed data/evals/eval_index.json
  professorId: null,
  professorName: "",
  courseId: null,
  courseName: "",
  records: [],          // records for current dept shard
  professorRecords: [],
  courseRecords: [],
  currentPage: 1,
  professorPage: 1,
  coursePage: 1,
};

// ── DOM refs ───────────────────────────────────────────────────────────────────

const stepCampus   = document.getElementById("stepCampus");
const stepDept     = document.getElementById("stepDept");
const stepFilter   = document.getElementById("stepFilter");
const stepProfessor = document.getElementById("stepProfessor");
const stepCourse = document.getElementById("stepCourse");
const campusCards  = document.getElementById("campusCards");
const campusLoading = document.getElementById("campusLoading");
const professorLaunch = document.getElementById("professorLaunch");
const professorLoading = document.getElementById("professorLoading");
const viewProfessorBtn = document.getElementById("viewProfessorBtn");
const courseLaunch = document.getElementById("courseLaunch");
const courseLoading = document.getElementById("courseLoading");
const viewCourseBtn = document.getElementById("viewCourseBtn");
const deptSearch   = document.getElementById("deptSearch");
const deptList     = document.getElementById("deptList");
const crumbCampus  = document.getElementById("crumbCampus");
const crumbDept    = document.getElementById("crumbDept");
const crumbSep1    = document.getElementById("crumbSep1");
const crumbSep2    = document.getElementById("crumbSep2");
const breadcrumb   = document.getElementById("breadcrumb");

const onChange = () => { state.currentPage = 1; updateResults(); };
const courseDD    = new FilterDropdown("courseDropdown",    onChange);
const professorDD = new FilterDropdown("professorDropdown", onChange);
const yearDD      = new FilterDropdown("yearDropdown",      onChange);
const quarterDD   = new FilterDropdown("quarterDropdown",   onChange);
const clearBtn    = document.getElementById("clearBtn");
const prevPageBtn    = document.getElementById("prevPageBtn");
const nextPageBtn    = document.getElementById("nextPageBtn");
const pageText       = document.getElementById("pageText");
const summaryText    = document.getElementById("summaryText");
const resultsBody    = document.getElementById("resultsBody");
const professorSummaryText = document.getElementById("professorSummaryText");
const professorEvalLink    = document.getElementById("professorEvalLink");
const professorResultsBody = document.getElementById("professorResultsBody");
const professorPageText = document.getElementById("professorPageText");
const professorPrevPageBtn = document.getElementById("professorPrevPageBtn");
const professorNextPageBtn = document.getElementById("professorNextPageBtn");
const professorResultsTitle = document.getElementById("professorResultsTitle");
const courseSummaryText = document.getElementById("courseSummaryText");
const courseResultsBody = document.getElementById("courseResultsBody");
const coursePageText = document.getElementById("coursePageText");
const coursePrevPageBtn = document.getElementById("coursePrevPageBtn");
const courseNextPageBtn = document.getElementById("courseNextPageBtn");
const courseResultsTitle = document.getElementById("courseResultsTitle");

// ── Routing (hash-based) ───────────────────────────────────────────────────────

const landingProfessorDD = new FilterDropdown("landingProfessorDropdown", () => {
  viewProfessorBtn.disabled = !landingProfessorDD.value;
});
const landingCourseDD = new FilterDropdown("landingCourseDropdown", () => {
  viewCourseBtn.disabled = !landingCourseDD.value;
});

function encodeHash(campus, dept, professorId) {
  if (professorId) return `#/professor/${professorId}`;
  const courseId = arguments.length > 3 ? arguments[3] : null;
  if (courseId) return `#/course/${courseId}`;
  if (!campus) return "#/";
  if (!dept)   return `#/${campus}`;
  return `#/${campus}/${dept}`;
}

function parseHash() {
  const hash = location.hash.replace(/^#\/?/, "");
  const parts = hash.split("/").filter(Boolean);
  if (parts[0] === "professor") {
    return { campus: null, dept: null, professorId: parts[1] || null, courseId: null };
  }
  if (parts[0] === "course") {
    return { campus: null, dept: null, professorId: null, courseId: parts[1] || null };
  }
  return { campus: parts[0] || null, dept: parts[1] || null, professorId: null, courseId: null };
}

function normalizeProfessorId(professorId) {
  if (!professorId) return null;
  const directMatch = (state.professorIndex?.professors || []).find(entry => entry.id === professorId);
  if (directMatch) return directMatch.id;

  const encoded = encodeURIComponent(professorId);
  const encodedMatch = (state.professorIndex?.professors || []).find(entry => entry.id === encoded);
  if (encodedMatch) return encodedMatch.id;

  try {
    const decoded = decodeURIComponent(professorId);
    const decodedMatch = (state.professorIndex?.professors || []).find(entry => entry.id === decoded);
    if (decodedMatch) return decodedMatch.id;

    const reencoded = encodeURIComponent(decoded);
    const reencodedMatch = (state.professorIndex?.professors || []).find(entry => entry.id === reencoded);
    if (reencodedMatch) return reencodedMatch.id;
  } catch {
    // Ignore malformed URI sequences and fall back to the original value.
  }

  return professorId;
}

function pushHash(campus, dept, professorId = null) {
  const courseId = arguments.length > 3 ? arguments[3] : null;
  history.pushState(null, "", encodeHash(campus, dept, professorId, courseId));
}

window.addEventListener("popstate", () => {
  const { campus, dept, professorId, courseId } = parseHash();
  if (professorId && state.professorIndex) {
    selectProfessor(professorId, false);
  } else if (courseId && state.courseIndex) {
    selectCourse(courseId, false);
  } else if (dept && state.catalogIndex) {
    selectDept(campus, dept, false);
  } else if (campus && state.catalogIndex) {
    selectCampus(campus, false);
  } else {
    showCampusStep();
  }
});

// ── Step visibility ────────────────────────────────────────────────────────────

function showOnly(step) {
  [stepCampus, stepDept, stepFilter, stepProfessor, stepCourse].forEach(s => s.classList.add("hidden"));
  step.classList.remove("hidden");
}

function updateBreadcrumb() {
  const hasCampus = !!state.campus;
  const hasDept   = !!state.dept;

  breadcrumb.classList.toggle("hidden", !hasCampus);

  const campusName = state.catalogIndex?.campuses?.[state.campus]?.name || state.campus || "";
  crumbCampus.textContent = campusName;
  crumbCampus.classList.toggle("crumb-link", state.view !== "campus");
  crumbSep1.classList.toggle("hidden", !hasCampus || state.view === "campus");

  const deptInfo = getDeptInfo(state.campus, state.dept);
  crumbDept.textContent = deptInfo ? `${deptInfo.name} (${state.dept?.toUpperCase()})` : "";
  crumbDept.classList.toggle("crumb-link", state.view === "filter");
  crumbSep2.classList.toggle("hidden", !hasDept || state.view !== "filter");

  document.querySelector(".crumb-filter")?.classList.toggle("hidden", state.view !== "filter");
}

crumbCampus.addEventListener("click", () => {
  if (state.view !== "campus") showCampusStep();
});
crumbDept.addEventListener("click", () => {
  if (state.view === "filter") showDeptStep();
});

// ── Campus step ────────────────────────────────────────────────────────────────

function showCampusStep() {
  state.view = "campus";
  state.campus = null;
  state.dept = null;
  state.professorId = null;
  state.professorName = "";
  state.courseId = null;
  state.courseName = "";
  state.records = [];
  state.professorRecords = [];
  state.courseRecords = [];
  showOnly(stepCampus);
  updateBreadcrumb();
  renderCampusCards();
  renderProfessorLaunch();
  renderCourseLaunch();
  pushHash(null, null, null, null);
}

function renderCampusCards() {
  if (!state.catalogIndex) return;
  campusLoading.style.display = "none";

  const campuses = state.catalogIndex.campuses || {};
  campusCards.innerHTML = "";

  const campusOrder = ["B", "T", "S"];
  const allKeys = campusOrder.filter(k => campuses[k]).concat(
    Object.keys(campuses).filter(k => !campusOrder.includes(k))
  );

  allKeys.forEach(code => {
    const info = campuses[code];
    const totalDepts = info.schools?.reduce((n, s) => n + s.depts.length, 0) || 0;
    const totalRecords = info.schools?.reduce(
      (n, s) => n + s.depts.reduce((m, d) => m + (d.recordCount || 0), 0), 0
    ) || 0;

    const card = document.createElement("button");
    card.className = "campus-card";
    card.type = "button";
    card.innerHTML = `
      <span class="campus-card-name">${info.name}</span>
      <span class="campus-card-meta">${totalDepts} department${totalDepts !== 1 ? "s" : ""}</span>
      <span class="campus-card-meta">${totalRecords.toLocaleString()} section records</span>
    `;
    card.addEventListener("click", () => selectCampus(code, true));
    campusCards.appendChild(card);
  });

  if (allKeys.length === 0) {
    campusCards.innerHTML =
      '<p class="empty-state">No campus data found. Run <code>npm run build:data -- --campus all</code> first.</p>';
  }
}

function renderProfessorLaunch() {
  if (!state.professorIndex || !(state.professorIndex.professors || []).length) {
    professorLaunch.classList.add("hidden");
    professorLoading.style.display = "block";
    return;
  }

  professorLaunch.classList.remove("hidden");
  professorLoading.style.display = "none";
  const values = state.professorIndex.professors.map(entry => entry.id);
  const labels = Object.fromEntries(
    state.professorIndex.professors.map(entry => [
      entry.id,
      `${entry.name} (${entry.recordCount.toLocaleString()} records)`,
    ])
  );
  landingProfessorDD.populate(values, "Select a professor", labels);
  viewProfessorBtn.disabled = !landingProfessorDD.value;
}

function renderCourseLaunch() {
  if (!state.courseIndex || !(state.courseIndex.courses || []).length) {
    courseLaunch.classList.add("hidden");
    courseLoading.style.display = "block";
    return;
  }

  courseLaunch.classList.remove("hidden");
  courseLoading.style.display = "none";
  const values = state.courseIndex.courses.map(entry => entry.id);
  const labels = Object.fromEntries(
    state.courseIndex.courses.map(entry => [
      entry.id,
      `${entry.name} (${entry.recordCount.toLocaleString()} offerings)`,
    ])
  );
  landingCourseDD.populate(values, "Select a course", labels);
  viewCourseBtn.disabled = !landingCourseDD.value;
}

function selectCampus(code, pushRoute = true) {
  state.campus = code;
  state.dept = null;
  state.view = "dept";
  if (pushRoute) pushHash(code, null);
  showDeptStep();
}

// ── Department step ────────────────────────────────────────────────────────────

function showDeptStep() {
  state.view = "dept";
  state.dept = null;
  state.records = [];
  showOnly(stepDept);
  updateBreadcrumb();
  renderDeptList("");
  deptSearch.value = "";
  deptSearch.focus();
}

function getDeptInfo(campus, deptCode) {
  if (!campus || !deptCode || !state.catalogIndex) return null;
  const campusData = state.catalogIndex.campuses?.[campus];
  if (!campusData) return null;
  for (const school of (campusData.schools || [])) {
    for (const dept of (school.depts || [])) {
      if (dept.code === deptCode) return { ...dept, school: school.name };
    }
  }
  return null;
}

function renderDeptList(query) {
  if (!state.catalogIndex) return;
  const campusData = state.catalogIndex.campuses?.[state.campus];
  if (!campusData) {
    deptList.innerHTML = '<p class="empty-state">No dept data for this campus.</p>';
    return;
  }

  const q = query.trim().toLowerCase();
  deptList.innerHTML = "";

  let totalVisible = 0;
  (campusData.schools || []).forEach(school => {
    const filtered = school.depts.filter(dept =>
      !q ||
      dept.name.toLowerCase().includes(q) ||
      dept.code.toLowerCase().includes(q)
    );
    if (!filtered.length) return;
    totalVisible += filtered.length;

    const groupEl = document.createElement("div");
    groupEl.className = "dept-group";
    groupEl.innerHTML = `<p class="dept-group-label">${school.name}</p>`;

    filtered.forEach(dept => {
      const btn = document.createElement("button");
      btn.className = "dept-item";
      btn.type = "button";
      const count = dept.recordCount ? `<span class="dept-count">${dept.recordCount.toLocaleString()} records</span>` : "";
      btn.innerHTML = `<span class="dept-name">${dept.name}</span>
                       <span class="dept-code">${dept.code.toUpperCase()}</span>
                       ${count}`;
      btn.addEventListener("click", () => selectDept(state.campus, dept.code, true));
      groupEl.appendChild(btn);
    });

    deptList.appendChild(groupEl);
  });

  if (totalVisible === 0) {
    deptList.innerHTML = '<p class="empty-state">No departments match your search.</p>';
  }
}

async function selectDept(campus, deptCode, pushRoute = true) {
  state.campus = campus;
  state.dept = deptCode;
  state.view = "filter";
  state.currentPage = 1;
  if (pushRoute) pushHash(campus, deptCode, null);

  showOnly(stepFilter);
  updateBreadcrumb();
  summaryText.textContent = "Loading department data…";
  resultsBody.innerHTML = "";
  state.records = [];

  await loadShard(campus, deptCode);
  updateResults();
}

async function selectProfessor(professorId, pushRoute = true) {
  const normalizedProfessorId = normalizeProfessorId(professorId);
  const professor = (state.professorIndex?.professors || []).find(entry => entry.id === normalizedProfessorId);
  state.view = "professor";
  state.campus = null;
  state.dept = null;
  state.professorId = normalizedProfessorId;
  state.professorName = professor?.name || normalizedProfessorId;
  state.professorPage = 1;
  if (pushRoute) pushHash(null, null, normalizedProfessorId);

  showOnly(stepProfessor);
  updateBreadcrumb();
  professorResultsTitle.textContent = state.professorName;
  professorSummaryText.textContent = "Loading professor data…";
  professorResultsBody.innerHTML = "";
  state.professorRecords = [];

  await loadProfessorRecords(normalizedProfessorId);
  updateProfessorResults();
}

function normalizeCourseId(courseId) {
  if (!courseId) return null;
  const directMatch = (state.courseIndex?.courses || []).find(entry => entry.id === courseId);
  if (directMatch) return directMatch.id;

  const encoded = encodeURIComponent(courseId);
  const encodedMatch = (state.courseIndex?.courses || []).find(entry => entry.id === encoded);
  if (encodedMatch) return encodedMatch.id;

  try {
    const decoded = decodeURIComponent(courseId);
    const decodedMatch = (state.courseIndex?.courses || []).find(entry => entry.id === decoded);
    if (decodedMatch) return decodedMatch.id;

    const reencoded = encodeURIComponent(decoded);
    const reencodedMatch = (state.courseIndex?.courses || []).find(entry => entry.id === reencoded);
    if (reencodedMatch) return reencodedMatch.id;
  } catch {
    // Ignore malformed URI sequences and fall back to the original value.
  }

  return courseId;
}

async function selectCourse(courseId, pushRoute = true) {
  const normalizedCourseId = normalizeCourseId(courseId);
  const course = (state.courseIndex?.courses || []).find(entry => entry.id === normalizedCourseId);
  state.view = "course";
  state.campus = null;
  state.dept = null;
  state.courseId = normalizedCourseId;
  state.courseName = course?.name || normalizedCourseId;
  state.coursePage = 1;
  if (pushRoute) pushHash(null, null, null, normalizedCourseId);

  showOnly(stepCourse);
  updateBreadcrumb();
  courseResultsTitle.textContent = state.courseName;
  courseSummaryText.textContent = "Loading course data…";
  courseResultsBody.innerHTML = "";
  state.courseRecords = [];

  await loadCourseRecords(normalizedCourseId);
  updateCourseResults();
}

// ── Shard loading ──────────────────────────────────────────────────────────────

async function loadShard(campus, deptCode) {
  try {
    const resp = await fetch(withDataVersion(`../data/shards/${campus}/${deptCode}.json`), { cache: "no-store" });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const payload = await resp.json();
    state.records = payload.records || [];
  } catch (err) {
    summaryText.textContent = `Could not load data for ${deptCode.toUpperCase()}. Run the build script first.`;
    state.records = [];
  }
}

async function loadProfessorRecords(professorId) {
  try {
    const fileProfessorId = encodeURIComponent(professorId);
    const resp = await fetch(withDataVersion(`../data/professors/${fileProfessorId}.json`), { cache: "no-store" });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const payload = await resp.json();
    state.professorRecords = payload.records || [];
  } catch {
    professorSummaryText.textContent = `Could not load data for ${state.professorName}. Run the build script first.`;
    state.professorRecords = [];
  }
}

async function loadCourseRecords(courseId) {
  try {
    const fileCourseId = encodeURIComponent(courseId);
    const resp = await fetch(withDataVersion(`../data/courses/${fileCourseId}.json`), { cache: "no-store" });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const payload = await resp.json();
    state.courseRecords = payload.records || [];
  } catch {
    courseSummaryText.textContent = `Could not load data for ${state.courseName}. Run the build script first.`;
    state.courseRecords = [];
  }
}

// ── Filter logic (unchanged from original) ────────────────────────────────────

function byLocale(a, b) { return a.localeCompare(b); }

function professorLink(name) {
  if (!name || name === "TBA") return name || "TBA";
  const prof = (state.professorIndex?.professors || []).find(p => p.name === name);
  if (!prof) return name;
  const safeId = prof.id.replace(/"/g, "&quot;");
  return `<button class="prof-link" data-prof-id="${safeId}">${name}</button>`;
}

function quarterSort(a, b) {
  return QUARTER_ORDER.indexOf(a) - QUARTER_ORDER.indexOf(b);
}

function termSortKey(termCode) {
  const prefix = String(termCode || "").slice(0, 3).toUpperCase();
  const year   = Number(String(termCode || "").slice(3));
  if (!Number.isFinite(year)) return { academicYear: 9999, quarterIndex: 99 };
  const orderMap = { AUT: 0, WIN: 1, SPR: 2, SUM: 3 };
  const quarterIndex = Object.hasOwn(orderMap, prefix) ? orderMap[prefix] : 99;
  const academicYear = prefix === "AUT" ? year : year - 1;
  return { academicYear, quarterIndex };
}

function sortCourseCodes(a, b) {
  const numA = Number((a.match(/\d+/) || [0])[0]);
  const numB = Number((b.match(/\d+/) || [0])[0]);
  return numA - numB || a.localeCompare(b);
}

function getQuarterLabel(termCode) {
  const prefix = String(termCode || "").slice(0, 3).toUpperCase();
  return TERM_TO_QUARTER[prefix] || "Other";
}

function getYearLabel(termCode) {
  const year = String(termCode || "").slice(3);
  return /^\d{4}$/.test(year) ? year : "";
}

function sortRecordsForDisplay(list) {
  return [...list].sort((a, b) => {
    const aKey = termSortKey(a.term);
    const bKey = termSortKey(b.term);
    if (aKey.academicYear !== bKey.academicYear) return bKey.academicYear - aKey.academicYear;
    if (aKey.quarterIndex !== bKey.quarterIndex) return bKey.quarterIndex - aKey.quarterIndex;
    return sortCourseCodes(a.course, b.course) || byLocale(a.instructor, b.instructor) || byLocale(a.section, b.section);
  });
}

function getActiveFilters() {
  return {
    course:    courseDD.value,
    quarter:   quarterDD.value,
    year:      yearDD.value,
    professor: professorDD.value,
  };
}

function filteredRecords(filters, ignoreKey = "") {
  return state.records.filter(r => {
    if (ignoreKey !== "course"    && filters.course    && r.course !== filters.course) return false;
    if (ignoreKey !== "quarter"   && filters.quarter   && getQuarterLabel(r.term) !== filters.quarter) return false;
    if (ignoreKey !== "year"      && filters.year      && getYearLabel(r.term) !== filters.year) return false;
    if (ignoreKey !== "professor" && filters.professor && r.instructor !== filters.professor) return false;
    return true;
  });
}

function refreshFilterOptions() {
  const filters = getActiveFilters();

  const courseValues = [...new Set(filteredRecords(filters, "course").map(r => r.course))].sort(sortCourseCodes);
  const courseLabels = Object.fromEntries(
    courseValues.map(course => {
      const match = state.records.find(r => r.course === course && r.courseTitle);
      return [course, match ? `${course} — ${match.courseTitle}` : course];
    })
  );
  const quarterValues = [...new Set(filteredRecords(filters, "quarter").map(r => getQuarterLabel(r.term)))].sort(quarterSort);
  const yearValues    = [...new Set(filteredRecords(filters, "year").map(r => getYearLabel(r.term)).filter(Boolean))].sort(byLocale);
  const profValues    = [...new Set(filteredRecords(filters, "professor").map(r => r.instructor))].sort(byLocale);

  courseDD.populate(courseValues,   "Courses",    courseLabels);
  quarterDD.populate(quarterValues, "Quarters");
  yearDD.populate(yearValues,       "Years");
  professorDD.populate(profValues,  "Professors");
}

function renderRows(filtered) {
  if (!filtered.length) {
    resultsBody.innerHTML = '<tr><td colspan="6">No matches found for that search.</td></tr>';
    pageText.textContent = "Page 0 of 0";
    prevPageBtn.disabled = true;
    nextPageBtn.disabled = true;
    return;
  }

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  if (state.currentPage > totalPages) state.currentPage = totalPages;
  if (state.currentPage < 1)         state.currentPage = 1;

  const start = (state.currentPage - 1) * PAGE_SIZE;
  const page  = filtered.slice(start, start + PAGE_SIZE);

  resultsBody.innerHTML = page.map(r => `
    <tr>
      <td>${r.course}</td>
      <td>${r.section}</td>
      <td>${r.courseTitle}</td>
      <td>${professorLink(r.instructor)}</td>
      <td>${getYearLabel(r.term)}</td>
      <td>${getQuarterLabel(r.term)}</td>
    </tr>
  `).join("");

  pageText.textContent = `Page ${state.currentPage} of ${totalPages}`;
  prevPageBtn.disabled = state.currentPage <= 1;
  nextPageBtn.disabled = state.currentPage >= totalPages;
}

function updateResults() {
  refreshFilterOptions();
  const filters  = getActiveFilters();
  const filtered = sortRecordsForDisplay(filteredRecords(filters));
  summaryText.textContent = `Showing ${filtered.length} of ${state.records.length} section records.`;
  renderRows(filtered);
}

function sortProfessorRecords(list) {
  return [...list].sort((a, b) => {
    const aKey = termSortKey(a.term);
    const bKey = termSortKey(b.term);
    if (aKey.academicYear !== bKey.academicYear) return bKey.academicYear - aKey.academicYear;
    if (aKey.quarterIndex !== bKey.quarterIndex) return bKey.quarterIndex - aKey.quarterIndex;
    return byLocale(a.campusName || a.campus, b.campusName || b.campus)
      || sortCourseCodes(a.course, b.course)
      || byLocale(a.section, b.section);
  });
}

function renderProfessorRows(filtered) {
  if (!filtered.length) {
    professorResultsBody.innerHTML = '<tr><td colspan="6">No courses found for this professor.</td></tr>';
    professorPageText.textContent = 'Page 0 of 0';
    professorPrevPageBtn.disabled = true;
    professorNextPageBtn.disabled = true;
    return;
  }

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  if (state.professorPage > totalPages) state.professorPage = totalPages;
  if (state.professorPage < 1) state.professorPage = 1;

  const start = (state.professorPage - 1) * PAGE_SIZE;
  const page = filtered.slice(start, start + PAGE_SIZE);

  professorResultsBody.innerHTML = page.map(r => `
    <tr>
      <td>${r.campusName || r.campus}</td>
      <td>${r.course}</td>
      <td>${r.section}</td>
      <td>${r.courseTitle}</td>
      <td>${getYearLabel(r.term)}</td>
      <td>${getQuarterLabel(r.term)}</td>
    </tr>
  `).join("");

  professorPageText.textContent = `Page ${state.professorPage} of ${totalPages}`;
  professorPrevPageBtn.disabled = state.professorPage <= 1;
  professorNextPageBtn.disabled = state.professorPage >= totalPages;
}

function updateProfessorResults() {
  const filtered = sortProfessorRecords(state.professorRecords);
  professorSummaryText.textContent = `Showing ${filtered.length} section records for ${state.professorName}.`;
  renderProfessorRows(filtered);

  const evalIds = state.evalIndex?.instructors || [];
  if (state.professorId && evalIds.includes(state.professorId)) {
    professorEvalLink.href = `./evals/${state.professorId}.html`;
    professorEvalLink.hidden = false;
  } else {
    professorEvalLink.hidden = true;
  }
}

function sortCourseRecords(list) {
  return [...list].sort((a, b) => {
    const aKey = termSortKey(a.term);
    const bKey = termSortKey(b.term);
    if (aKey.academicYear !== bKey.academicYear) return bKey.academicYear - aKey.academicYear;
    if (aKey.quarterIndex !== bKey.quarterIndex) return bKey.quarterIndex - aKey.quarterIndex;
    return byLocale(a.instructor || "TBA", b.instructor || "TBA")
      || byLocale(a.section || "", b.section || "");
  });
}

function renderCourseRows(filtered) {
  if (!filtered.length) {
    courseResultsBody.innerHTML = '<tr><td colspan="7">No offerings found for this course.</td></tr>';
    coursePageText.textContent = 'Page 0 of 0';
    coursePrevPageBtn.disabled = true;
    courseNextPageBtn.disabled = true;
    return;
  }

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  if (state.coursePage > totalPages) state.coursePage = totalPages;
  if (state.coursePage < 1) state.coursePage = 1;

  const start = (state.coursePage - 1) * PAGE_SIZE;
  const page = filtered.slice(start, start + PAGE_SIZE);

  courseResultsBody.innerHTML = page.map(r => `
    <tr>
      <td>${r.campusName || r.campus}</td>
      <td>${r.course}</td>
      <td>${r.section}</td>
      <td>${r.courseTitle}</td>
      <td>${professorLink(r.instructor)}</td>
      <td>${getYearLabel(r.term)}</td>
      <td>${getQuarterLabel(r.term)}</td>
    </tr>
  `).join("");

  coursePageText.textContent = `Page ${state.coursePage} of ${totalPages}`;
  coursePrevPageBtn.disabled = state.coursePage <= 1;
  courseNextPageBtn.disabled = state.coursePage >= totalPages;
}

function updateCourseResults() {
  const filtered = sortCourseRecords(state.courseRecords);
  courseSummaryText.textContent = `Showing ${filtered.length} offerings for ${state.courseName}.`;
  renderCourseRows(filtered);
}

// ── Event listeners ────────────────────────────────────────────────────────────

resultsBody.addEventListener("click", e => {
  const btn = e.target.closest(".prof-link");
  if (btn) selectProfessor(btn.dataset.profId);
});

courseResultsBody.addEventListener("click", e => {
  const btn = e.target.closest(".prof-link");
  if (btn) selectProfessor(btn.dataset.profId);
});

document.getElementById("backToCampus").addEventListener("click", showCampusStep);
document.getElementById("backToDept").addEventListener("click", () => {
  state.view = "dept";
  showDeptStep();
  pushHash(state.campus, null);
});
document.getElementById("backToHome").addEventListener("click", showCampusStep);
document.getElementById("backToHomeFromCourse").addEventListener("click", showCampusStep);
viewProfessorBtn.addEventListener("click", () => {
  if (landingProfessorDD.value) selectProfessor(landingProfessorDD.value, true);
});
viewCourseBtn.addEventListener("click", () => {
  if (landingCourseDD.value) selectCourse(landingCourseDD.value, true);
});

deptSearch.addEventListener("input", () => renderDeptList(deptSearch.value));

prevPageBtn.addEventListener("click", () => { state.currentPage -= 1; updateResults(); });
nextPageBtn.addEventListener("click", () => { state.currentPage += 1; updateResults(); });
professorPrevPageBtn.addEventListener("click", () => { state.professorPage -= 1; updateProfessorResults(); });
professorNextPageBtn.addEventListener("click", () => { state.professorPage += 1; updateProfessorResults(); });
coursePrevPageBtn.addEventListener("click", () => { state.coursePage -= 1; updateCourseResults(); });
courseNextPageBtn.addEventListener("click", () => { state.coursePage += 1; updateCourseResults(); });

clearBtn.addEventListener("click", () => {
  courseDD.value    = "";
  quarterDD.value   = "";
  yearDD.value      = "";
  professorDD.value = "";
  state.currentPage = 1;
  updateResults();
  courseDD.focus();
});

// ── Boot ───────────────────────────────────────────────────────────────────────

async function loadCatalogIndex() {
  try {
    const resp = await fetch(withDataVersion("../data/catalog_index.json"), { cache: "no-store" });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  } catch {
    return null;
  }
}

async function loadProfessorIndex() {
  try {
    const resp = await fetch(withDataVersion("../data/professor_index.json"), { cache: "no-store" });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  } catch {
    return null;
  }
}

async function loadCourseIndex() {
  try {
    const resp = await fetch(withDataVersion("../data/course_index.json"), { cache: "no-store" });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  } catch {
    return null;
  }
}

async function loadEvalIndex() {
  try {
    const resp = await fetch(withDataVersion("../data/evals/eval_index.json"), { cache: "no-store" });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  } catch {
    return null;
  }
}

async function start() {
  // Try new multi-campus index first
  const [index, professorIndex, courseIndex, evalIndex] = await Promise.all([
    loadCatalogIndex(),
    loadProfessorIndex(),
    loadCourseIndex(),
    loadEvalIndex(),
  ]);

  if (index && Object.keys(index.campuses || {}).length > 0) {
    state.catalogIndex = index;
    state.professorIndex = professorIndex;
    state.courseIndex = courseIndex;
    state.evalIndex = evalIndex;

    // Check if deep link in hash
    const { campus, dept, professorId, courseId } = parseHash();
    if (professorId && state.professorIndex) {
      await selectProfessor(professorId, false);
    } else if (courseId && state.courseIndex) {
      await selectCourse(courseId, false);
    } else if (dept && campus) {
      await selectDept(campus, dept, false);
    } else if (campus) {
      selectCampus(campus, false);
    } else {
      showCampusStep();
    }
    return;
  }

  // Fallback: legacy catalog.json (Bothell CSS only)
  try {
    const resp = await fetch(withDataVersion("../data/catalog.json"), { cache: "no-store" });
    if (!resp.ok) throw new Error("Failed to load catalog data");
    const payload = await resp.json();
    state.records = payload.records || [];

    // Show filter UI directly (legacy behaviour)
    showOnly(stepFilter);
    breadcrumb.classList.add("hidden");
    summaryText.textContent = "Loaded legacy CSS data (Bothell only).";
    updateResults();
  } catch {
    summaryText.textContent = "Could not load data. Run the build script first.";
    showOnly(stepFilter);
    breadcrumb.classList.add("hidden");
  }
}

start();
