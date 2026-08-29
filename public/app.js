var API_URL = window.location.origin;
var currentTemp = 21;
var defrostEnabled = false;
var climateActive = false;
var selectedDays = [];
var editingScheduleId = null;
var lastSuccessAt = 0;
var isRefreshing = false;

function showAlert(message, type) {
    var alerts = document.getElementById('alerts');
    var alert = document.createElement('div');
    alert.className = 'alert alert-' + (type || 'success');
    alert.textContent = message;
    alerts.appendChild(alert);
    setTimeout(function () { alert.classList.add('leaving'); }, 4200);
    setTimeout(function () { alert.remove(); }, 4600);
}

function setFieldError(id, message) {
    var el = document.getElementById(id);
    if (!el) return;
    if (message) {
        el.textContent = message;
        el.classList.remove('hidden');
    } else {
        el.textContent = '';
        el.classList.add('hidden');
    }
}

function clearFieldErrors() {
    setFieldError('scheduleNameError', '');
    setFieldError('scheduleTimeError', '');
    setFieldError('scheduleTempError', '');
    setFieldError('scheduleDaysError', '');
}

function pad2(n) { n = String(n); return n.length < 2 ? '0' + n : n; }

function initTimePicker() {
    var h = document.getElementById('scheduleHour');
    var m = document.getElementById('scheduleMin');
    if (!h || !m || h.options.length) return;
    for (var i = 0; i < 24; i++) h.add(new Option(pad2(i), i));
    for (var j = 0; j < 60; j++) m.add(new Option(pad2(j), j));
    setScheduleTime('07:00');
}

function getScheduleTime() {
    return pad2(document.getElementById('scheduleHour').value) + ':' +
           pad2(document.getElementById('scheduleMin').value);
}

function setScheduleTime(hhmm) {
    var parts = String(hhmm || '07:00').split(':');
    document.getElementById('scheduleHour').value = parseInt(parts[0], 10) || 0;
    document.getElementById('scheduleMin').value = parseInt(parts[1], 10) || 0;
}

function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(function (t) { t.classList.remove('active'); });
    document.querySelectorAll('.tab-content').forEach(function (c) { c.classList.remove('active'); });
    document.body.setAttribute('data-tab', tab);

    if (tab === 'status') {
        document.querySelector('.tab:nth-child(1)').classList.add('active');
        document.getElementById('statusTab').classList.add('active');
    } else if (tab === 'schedule') {
        document.querySelector('.tab:nth-child(2)').classList.add('active');
        document.getElementById('scheduleTab').classList.add('active');
        loadSchedules();
    }

    if (window.history && history.replaceState) {
        history.replaceState(null, '', tab === 'schedule' ? '#schema' : location.pathname);
    }
}

function updateBatteryGauge(percent, charging) {
    var circumference = 2 * Math.PI * 90;
    var offset = circumference - (percent / 100) * circumference;
    document.getElementById('batteryGaugeFill').style.strokeDashoffset = offset;
    document.getElementById('batteryPercent').textContent = percent + '%';

    var gauge = document.getElementById('batteryGauge');
    var label = document.getElementById('batteryLabel');
    var stop1 = document.getElementById('gradStop1');
    var stop2 = document.getElementById('gradStop2');
    var stop3 = document.getElementById('gradStop3');

    if (charging) {
        gauge.classList.add('charging');
        label.textContent = 'Laddar';
        stop1.style.stopColor = '#6ff2c0';
        stop2.style.stopColor = '#3ddc84';
        stop3.style.stopColor = '#16b364';
    } else {
        gauge.classList.remove('charging');
        label.textContent = 'Batteri';
        stop1.style.stopColor = '#8ff3e6';
        stop2.style.stopColor = '#5fd0c5';
        stop3.style.stopColor = '#5aa8f4';
    }
}

function updateConnectionStatus(connected) {
    var dot = document.getElementById('connectionDot');
    if (connected) {
        dot.className = 'connection-dot connected';
        dot.title = 'Ansluten till Kia';
    } else {
        dot.className = 'connection-dot disconnected';
        dot.title = 'Ej ansluten';
    }
}

function updateVehicleAlerts(doors, windows, locked) {
    var container = document.getElementById('vehicleAlerts');
    var items = document.getElementById('vehicleAlertItems');
    var alerts = [];

    if (!locked) {
        alerts.push({ text: 'Olåst', type: 'warning' });
    }

    var doorNames = { driver: 'Förardörr', passenger: 'Passagerardörr', backLeft: 'V bak dörr', backRight: 'H bak dörr', hood: 'Huv', trunk: 'Bagage' };
    for (var key in doors) {
        if (doors[key]) {
            alerts.push({ text: doorNames[key] + ' öppen', type: 'danger' });
        }
    }

    var windowNames = { driver: 'Förarfönster', passenger: 'Passagerarfönster', backLeft: 'V bak fönster', backRight: 'H bak fönster' };
    for (var key in windows) {
        if (windows[key]) {
            alerts.push({ text: windowNames[key] + ' öppet', type: 'danger' });
        }
    }

    if (alerts.length === 0) {
        container.classList.add('hidden');
        return;
    }

    items.textContent = '';
    alerts.forEach(function (a) {
        var chip = document.createElement('div');
        chip.className = 'alert-item ' + a.type;
        chip.textContent = a.text;
        items.appendChild(chip);
    });
    container.classList.remove('hidden');
}

function renderStatus(d) {
    document.body.setAttribute('data-state', d.charging ? 'charging' : (d.climateActive ? 'climate' : 'idle'));

    updateBatteryGauge(d.battery, d.charging);
    document.getElementById('range').textContent = d.range + ' km';

    var lockBadge = document.getElementById('lockBadge');
    lockBadge.textContent = d.locked ? 'Låst' : 'Olåst';
    lockBadge.className = d.locked ? 'badge badge-success' : 'badge badge-warning';

    var climateBadge = document.getElementById('climateBadge');
    if (d.climateActive) {
        climateBadge.textContent = 'Påslagen';
        climateBadge.className = 'badge badge-success';
        climateActive = true;
        updateClimateButtons(true);
    } else {
        climateBadge.textContent = 'Av';
        climateBadge.className = 'badge badge-gray';
        climateActive = false;
        updateClimateButtons(false);
    }

    updateVehicleAlerts(d.doors, d.windows, d.locked);
    updateExtendedStatus(d);
}

function fmtNum(n) {
    return (n === null || n === undefined) ? null : Math.round(n).toLocaleString('sv-SE');
}

function updateExtendedStatus(d) {
    document.getElementById('odometer').textContent =
        (d.odometer !== null && d.odometer !== undefined) ? fmtNum(d.odometer) + ' km' : '–';

    document.getElementById('chargeLimitValue').textContent =
        (d.chargeLimitAc !== null && d.chargeLimitAc !== undefined) ? d.chargeLimitAc + '%' : '–';

    var durItem = document.getElementById('chargeDurationItem');
    if (d.charging && d.chargeDurationMin) {
        var h = Math.floor(d.chargeDurationMin / 60);
        var m = d.chargeDurationMin % 60;
        document.getElementById('chargeDuration').textContent = h > 0 ? (h + ' h ' + m + ' min') : (m + ' min');
        durItem.classList.remove('hidden');
    } else {
        durItem.classList.add('hidden');
    }

    var cu = document.getElementById('carUpdated');
    if (d.carUpdatedAt) {
        var dt = new Date(d.carUpdatedAt);
        cu.textContent = 'Data från bilen ' + dt.toLocaleString('sv-SE',
            { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false });
    } else {
        cu.textContent = '';
    }

    var slider = document.getElementById('chargeLimitSlider');
    if (d.chargeLimitAc !== null && d.chargeLimitAc !== undefined && document.activeElement !== slider) {
        slider.value = d.chargeLimitAc;
        document.getElementById('chargeLimitSliderValue').textContent = d.chargeLimitAc + '%';
    }

    updateCarDetails(d);
}

function has(v) { return v !== null && v !== undefined && v !== ''; }

function addDetail(parent, label, value) {
    if (!has(value)) return;
    var item = document.createElement('div');
    item.className = 'status-item';
    var l = document.createElement('div');
    l.className = 'status-label';
    l.textContent = label;
    var v = document.createElement('div');
    v.className = 'status-value';
    v.textContent = value;
    item.appendChild(l);
    item.appendChild(v);
    parent.appendChild(item);
}

var carDetailsShown = false;

function updateCarDetails(d) {
    if (!carDetailsShown) return;
    var panel = document.getElementById('carDetails');
    panel.textContent = '';

    addDetail(panel, '12V-batteri', has(d.twelveVBattery) ? d.twelveVBattery + '%' : null);
    addDetail(panel, 'Förbrukning 30 d', has(d.consumption30d) ? d.consumption30d + ' Wh/km' : null);

    if (d.today && has(d.today.distance)) {
        var t = d.today;
        var txt = fmtNum(t.distance) + ' ' + (t.distanceUnit || 'km');
        if (has(t.consumedKwh)) txt += ' · ' + String(t.consumedKwh).replace('.', ',') + ' kWh';
        addDetail(panel, 'Idag', txt);
    }

    addDetail(panel, 'Snabbladdning 10–80 %', has(d.fastChargeMin) ? '~' + d.fastChargeMin + ' min' : null);
    addDetail(panel, 'Räckvidd vid ' + (has(d.chargeLimitAc) ? d.chargeLimitAc + ' %' : 'mål'),
              has(d.targetRangeAc) ? fmtNum(d.targetRangeAc) + ' km' : null);
    addDetail(panel, 'Batterihälsa', has(d.batterySoh) ? d.batterySoh + '%' : null);
    addDetail(panel, 'Utetemp', has(d.outsideTemp) ? d.outsideTemp + '°' : null);

    var tp = d.tirePressure || {};
    if (has(tp.fl) || has(tp.fr) || has(tp.rl) || has(tp.rr)) {
        var u = tp.unit ? ' ' + tp.unit : '';
        var dash = function (x) { return has(x) ? x : '–'; };
        addDetail(panel, 'Däcktryck F / B',
            dash(tp.fl) + '/' + dash(tp.fr) + ' · ' + dash(tp.rl) + '/' + dash(tp.rr) + u);
    }

    panel.classList.toggle('hidden', panel.children.length === 0);
}

function refreshFromCar() {
    var btn = document.getElementById('refreshCarBtn');
    var txt = document.getElementById('refreshCarText');
    if (btn.disabled) return;
    btn.disabled = true;
    btn.classList.add('loading');
    txt.textContent = 'Väcker bilen…';

    fetch(API_URL + '/api/refresh', { method: 'POST' })
        .then(function (r) {
            return r.json().then(function (payload) {
                return { ok: r.ok, status: r.status, data: payload };
            });
        })
        .then(function (result) {
            if (result.data && result.data.success) {
                lastSuccessAt = Date.now();
                updateConnectionStatus(true);
                carDetailsShown = true;
                renderStatus(result.data.data);
                showAlert('Uppdaterad från bilen', 'success');
            } else {
                showAlert((result.data && result.data.message) || 'Kunde inte uppdatera från bilen', 'error');
            }
        })
        .catch(function (e) { showAlert('Kunde inte uppdatera från bilen', 'error'); })
        .finally(function () {
            btn.disabled = false;
            btn.classList.remove('loading');
            txt.textContent = 'Uppdatera från bilen';
        });
}

function saveChargeLimit() {
    var v = parseInt(document.getElementById('chargeLimitSlider').value, 10);
    var btn = document.getElementById('saveChargeLimitBtn');
    if (btn.disabled) return;
    btn.disabled = true;
    var orig = btn.textContent;
    btn.textContent = 'Sparar…';

    fetch(API_URL + '/api/charge-limits', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ac: v, dc: v })
    })
    .then(function (r) { return r.json(); })
    .then(function (result) {
        showAlert(result.message, result.success ? 'success' : 'error');
        if (result.success) setTimeout(refreshStatus, 3000);
    })
    .catch(function (e) { showAlert('Kunde inte spara laddgräns', 'error'); })
    .finally(function () {
        btn.disabled = false;
        btn.textContent = orig;
    });
}

function refreshStatus() {
    if (isRefreshing) return;
    isRefreshing = true;

    var gauge = document.getElementById('batteryGauge');
    gauge.classList.add('polling');

    fetch(API_URL + '/api/status')
        .then(function (r) {
            return r.json().then(function (payload) {
                return { ok: r.ok, status: r.status, data: payload };
            });
        })
        .then(function (result) {
            if (result.data && result.data.success) {
                lastSuccessAt = Date.now();
                updateConnectionStatus(true);
                renderStatus(result.data.data);
            } else {
                if (result.status === 429 && result.data && result.data.retry_after) {
                    if (!lastSuccessAt || Date.now() - lastSuccessAt > 120000) {
                        updateConnectionStatus(false);
                    }
                    showAlert(result.data.message, 'error');
                } else {
                    if (!lastSuccessAt || Date.now() - lastSuccessAt > 120000) {
                        updateConnectionStatus(false);
                    }
                    showAlert((result.data && result.data.message) || 'Kunde inte hämta status', 'error');
                }
            }
        })
        .catch(function (e) {
            if (!lastSuccessAt || Date.now() - lastSuccessAt > 120000) {
                updateConnectionStatus(false);
            }
            showAlert('Kunde inte hämta status', 'error');
        })
        .finally(function () {
            isRefreshing = false;
            gauge.classList.remove('polling');
        });
}

function adjustTemp(delta) {
    currentTemp = Math.max(16, Math.min(30, currentTemp + delta));
    document.getElementById('targetTemp').textContent = currentTemp + '°';
}

function toggleDefrost() {
    defrostEnabled = !defrostEnabled;
    document.getElementById('defrostText').textContent = 'Avfrostning: ' + (defrostEnabled ? 'På' : 'Av');
    var b = document.getElementById('defrostBtn');
    if (b) b.classList.toggle('is-on', defrostEnabled);
}

function startClimate() {
    var btn = document.getElementById('startClimateBtn');
    btn.disabled = true;
    btn.textContent = 'Startar…';

    fetch(API_URL + '/api/climate/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ temperature: currentTemp, defrost: defrostEnabled, heating: true })
    })
    .then(function (r) { return r.json(); })
    .then(function (result) {
        btn.disabled = false;
        btn.textContent = 'Starta klimat';
        showAlert(result.message, result.success ? 'success' : 'error');
        if (result.success) {
            climateActive = true;
            updateClimateButtons(true);
            setTimeout(refreshStatus, 5000);
        }
    })
    .catch(function (e) {
        btn.disabled = false;
        btn.textContent = 'Starta klimat';
        showAlert('Fel vid klimatstart', 'error');
    });
}

function stopClimate() {
    var btn = document.getElementById('stopClimateBtn');
    btn.disabled = true;
    btn.textContent = 'Stoppar…';

    fetch(API_URL + '/api/climate/stop', { method: 'POST' })
        .then(function (r) { return r.json(); })
        .then(function (result) {
            btn.disabled = false;
            btn.textContent = 'Stoppa klimat';
            showAlert(result.message, result.success ? 'success' : 'error');
            if (result.success) {
                climateActive = false;
                updateClimateButtons(false);
                setTimeout(refreshStatus, 5000);
            }
        })
        .catch(function (e) {
            btn.disabled = false;
            btn.textContent = 'Stoppa klimat';
            showAlert('Fel vid klimatstopp', 'error');
        });
}

function updateClimateButtons(active) {
    document.getElementById('startClimateBtn').classList.toggle('hidden', active);
    document.getElementById('stopClimateBtn').classList.toggle('hidden', !active);
}

function startCharging() {
    fetch(API_URL + '/api/charging/start', { method: 'POST' })
        .then(function (r) { return r.json(); })
        .then(function (result) {
            showAlert(result.message, result.success ? 'success' : 'error');
            if (result.success) setTimeout(refreshStatus, 5000);
        })
        .catch(function (e) { showAlert('Fel vid laddningsstart', 'error'); });
}

function stopCharging() {
    fetch(API_URL + '/api/charging/stop', { method: 'POST' })
        .then(function (r) { return r.json(); })
        .then(function (result) {
            showAlert(result.message, result.success ? 'success' : 'error');
            if (result.success) setTimeout(refreshStatus, 5000);
        })
        .catch(function (e) { showAlert('Fel vid laddningsstopp', 'error'); });
}

function loadSchedules() {
    fetch(API_URL + '/api/schedules')
        .then(function (r) { return r.json(); })
        .then(function (result) {
            if (result.success) displaySchedules(result.schedules);
        })
        .catch(function (e) { console.error('Kunde inte ladda scheman:', e); });
}

function displaySchedules(schedules) {
    var list = document.getElementById('scheduleList');
    list.textContent = '';
    var dayLabels = ['M', 'T', 'O', 'T', 'F', 'L', 'S'];

    if (!schedules.length) {
        var empty = document.createElement('p');
        empty.className = 'empty';
        empty.textContent = 'Inga schemalagda starter än.';
        list.appendChild(empty);
        return;
    }

    schedules.forEach(function (s) {
        var card = document.createElement('div');
        card.className = 'sched' + (s.enabled ? '' : ' off');

        var main = document.createElement('div');
        main.className = 'sched-main';

        var time = document.createElement('div');
        time.className = 'sched-time';
        time.textContent = s.time;
        main.appendChild(time);

        var meta = document.createElement('div');
        meta.className = 'sched-meta';
        var nm = document.createElement('span');
        nm.className = 'sched-name';
        nm.textContent = s.name;
        var sub = document.createElement('span');
        sub.className = 'sched-sub';
        sub.textContent = s.temperature + '°C' + (s.defrost ? ' · avfrost' : '');
        meta.appendChild(nm);
        meta.appendChild(sub);
        main.appendChild(meta);
        card.appendChild(main);

        var dayRow = document.createElement('div');
        dayRow.className = 'day-row';
        for (var i = 0; i < 7; i++) {
            var dd = document.createElement('span');
            dd.className = 'day-dot' + (s.days.indexOf(i) !== -1 ? ' on' : '');
            dd.textContent = dayLabels[i];
            dayRow.appendChild(dd);
        }
        card.appendChild(dayRow);

        var actions = document.createElement('div');
        actions.className = 'sched-actions';

        var toggle = document.createElement('label');
        toggle.className = 'switch';
        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = !!s.enabled;
        cb.addEventListener('change', (function (id) {
            return function () { toggleScheduleEnabled(id, this.checked); };
        })(s.id));
        var track = document.createElement('span');
        track.className = 'switch-track';
        toggle.appendChild(cb);
        toggle.appendChild(track);
        actions.appendChild(toggle);

        var edit = document.createElement('button');
        edit.className = 'btn btn-secondary sm';
        edit.textContent = 'Ändra';
        edit.addEventListener('click', (function (id) {
            return function () { editSchedule(id); };
        })(s.id));
        actions.appendChild(edit);

        var del = document.createElement('button');
        del.className = 'btn btn-ghost sm';
        del.textContent = 'Ta bort';
        del.addEventListener('click', (function (id) {
            return function () { deleteSchedule(id); };
        })(s.id));
        actions.appendChild(del);

        card.appendChild(actions);
        list.appendChild(card);
    });
}

function showAddSchedule() {
    document.getElementById('formTitle').textContent = 'Nytt schema';
    document.getElementById('addScheduleForm').classList.remove('hidden');
    selectedDays = [0, 1, 2, 3, 4];
    updateDayBadges();
    editingScheduleId = null;
    document.getElementById('addScheduleForm').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function editSchedule(id) {
    fetch(API_URL + '/api/schedules')
        .then(function (r) { return r.json(); })
        .then(function (result) {
            if (result.success) {
                var schedule = result.schedules.find(function (s) { return s.id === id; });
                if (schedule) {
                    document.getElementById('formTitle').textContent = 'Redigera: ' + schedule.name;
                    document.getElementById('scheduleName').value = schedule.name;
                    setScheduleTime(schedule.time);
                    document.getElementById('scheduleTemp').value = schedule.temperature;
                    document.getElementById('scheduleDefrost').checked = schedule.defrost;
                    selectedDays = schedule.days;
                    updateDayBadges();
                    editingScheduleId = id;
                    document.getElementById('addScheduleForm').classList.remove('hidden');
                    document.getElementById('addScheduleForm').scrollIntoView({ behavior: 'smooth' });
                }
            }
        });
}

function cancelSchedule() {
    document.getElementById('addScheduleForm').classList.add('hidden');
    document.getElementById('scheduleName').value = 'Morgon';
    setScheduleTime('07:00');
    document.getElementById('scheduleTemp').value = '21';
    document.getElementById('scheduleDefrost').checked = false;
    selectedDays = [];
    editingScheduleId = null;
}

function toggleDay(day) {
    var idx = selectedDays.indexOf(day);
    if (idx === -1) {
        selectedDays.push(day);
    } else {
        selectedDays.splice(idx, 1);
    }
    updateDayBadges();
}

function updateDayBadges() {
    document.querySelectorAll('.day-badge').forEach(function (badge) {
        var day = parseInt(badge.getAttribute('data-day'));
        if (selectedDays.indexOf(day) !== -1) {
            badge.classList.add('active');
        } else {
            badge.classList.remove('active');
        }
    });
}

function saveSchedule() {
    clearFieldErrors();
    var hasError = false;

    var timeValue = getScheduleTime();
    var nameValue = document.getElementById('scheduleName').value.trim();
    var tempValue = parseInt(document.getElementById('scheduleTemp').value);

    if (!nameValue) {
        setFieldError('scheduleNameError', 'Ange ett namn.');
        hasError = true;
    }

    if (!timeValue || !timeValue.match(/^\d{2}:\d{2}$/)) {
        setFieldError('scheduleTimeError', 'Ogiltig tid. Använd HH:MM.');
        hasError = true;
    }

    if (isNaN(tempValue) || tempValue < 16 || tempValue > 30) {
        setFieldError('scheduleTempError', 'Temperatur: 16–30 °C.');
        hasError = true;
    }

    if (selectedDays.length === 0) {
        setFieldError('scheduleDaysError', 'Välj minst en dag.');
        hasError = true;
    }

    if (hasError) return;

    var schedule = {
        id: editingScheduleId || Date.now().toString(),
        name: nameValue,
        time: timeValue,
        temperature: tempValue,
        defrost: document.getElementById('scheduleDefrost').checked,
        days: selectedDays,
        enabled: true
    };

    fetch(API_URL + '/api/schedules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(schedule)
    })
    .then(function (r) { return r.json(); })
    .then(function (result) {
        if (result.success) {
            showAlert(editingScheduleId ? 'Schema uppdaterat' : 'Schema sparat', 'success');
            cancelSchedule();
            loadSchedules();
        } else {
            showAlert(result.message, 'error');
        }
    })
    .catch(function (e) { showAlert('Kunde inte spara', 'error'); });
}

function toggleScheduleEnabled(id, enabled) {
    fetch(API_URL + '/api/schedules/' + id + '/toggle', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: enabled })
    })
    .then(function (r) { return r.json(); })
    .then(function (result) {
        if (result.success) {
            showAlert(enabled ? 'Schema aktiverat' : 'Schema inaktiverat', 'success');
            loadSchedules();
        } else {
            showAlert(result.message, 'error');
        }
    })
    .catch(function (e) { showAlert('Kunde inte uppdatera schema', 'error'); });
}

function deleteSchedule(id) {
    if (!confirm('Ta bort denna schemastart?')) return;

    fetch(API_URL + '/api/schedules/' + id, { method: 'DELETE' })
        .then(function (r) { return r.json(); })
        .then(function (result) {
            if (result.success) {
                showAlert('Schema borttaget', 'success');
                loadSchedules();
            } else {
                showAlert(result.message, 'error');
            }
        })
        .catch(function (e) { showAlert('Kunde inte ta bort', 'error'); });
}

window.addEventListener('load', function () {
    initTimePicker();
    if (location.hash === '#schema') switchTab('schedule');
    refreshStatus();
});
