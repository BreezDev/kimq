document.addEventListener('DOMContentLoaded', () => {
    const availabilityContainer = document.querySelector('#availability');
    const dateInput = document.querySelector('#date');
    const employeeSelect = document.querySelector('#employee_id');
    const calendarEl = document.querySelector('#calendar');
    const monthLabel = document.querySelector('#calendar-month');
    const prevMonthBtn = document.querySelector('#prev-month');
    const nextMonthBtn = document.querySelector('#next-month');
    const depositBlurb = document.querySelector('#deposit-blurb');
    const serviceSelect = document.querySelector('#service_id');
    let currentMonth = new Date();

    const syncDepositCopy = () => {
        if (!serviceSelect || !depositBlurb) return;
        const option = serviceSelect.selectedOptions[0];
        if (!option) return;
        const deposit = option.dataset.deposit;
        depositBlurb.textContent = `Deposit due today: ${deposit} (Stripe test mode). Remaining balance is payable in studio.`;
    };

    const setDateValue = (date) => {
        const iso = date.toISOString().split('T')[0];
        if (dateInput) {
            dateInput.value = iso;
            dateInput.dispatchEvent(new Event('change'));
        }
        document.querySelectorAll('.day').forEach(d => d.classList.remove('selected'));
        const match = document.querySelector(`.day[data-date="${iso}"]`);
        if (match) match.classList.add('selected');
    };

    const renderCalendar = () => {
        if (!calendarEl || !monthLabel) return;
        calendarEl.innerHTML = '';
        const year = currentMonth.getFullYear();
        const month = currentMonth.getMonth();
        const firstDay = new Date(year, month, 1);
        const startDay = firstDay.getDay();
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        monthLabel.textContent = currentMonth.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });

        const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        dayNames.forEach(name => {
            const div = document.createElement('div');
            div.className = 'day heading';
            div.textContent = name;
            calendarEl.appendChild(div);
        });

        for (let i = 0; i < startDay; i++) {
            const spacer = document.createElement('div');
            spacer.className = 'day muted';
            calendarEl.appendChild(spacer);
        }

        const today = new Date();
        for (let d = 1; d <= daysInMonth; d++) {
            const cellDate = new Date(year, month, d);
            const iso = cellDate.toISOString().split('T')[0];
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'day';
            button.dataset.date = iso;
            button.textContent = d;
            if (cellDate < new Date(today.toDateString())) {
                button.disabled = true;
                button.classList.add('muted');
            }
            button.addEventListener('click', () => setDateValue(cellDate));
            calendarEl.appendChild(button);
        }

        if (!dateInput.value) {
            setDateValue(today);
        } else {
            setDateValue(new Date(dateInput.value));
        }
    };

    const renderSlots = (data) => {
        if (!availabilityContainer) return;
        availabilityContainer.innerHTML = '';
        data.forEach(block => {
            const wrapper = document.createElement('div');
            wrapper.className = 'card';
            const title = document.createElement('h3');
            title.textContent = block.employee_name;
            wrapper.appendChild(title);
            if (!block.slots.length) {
                const p = document.createElement('p');
                p.textContent = 'No openings for this day.';
                wrapper.appendChild(p);
            } else {
                const list = document.createElement('div');
                list.className = 'flex';
                block.slots.forEach(slot => {
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'btn';
                    btn.textContent = slot;
                    btn.addEventListener('click', () => {
                        const timeInput = document.querySelector('#time');
                        timeInput.value = slot;
                        employeeSelect.value = block.employee_id;
                        document.querySelector('#book-form').scrollIntoView({ behavior: 'smooth' });
                    });
                    list.appendChild(btn);
                });
                wrapper.appendChild(list);
            }
            availabilityContainer.appendChild(wrapper);
        });
    };

    const fetchAvailability = () => {
        if (!dateInput || !availabilityContainer) return;
        const params = new URLSearchParams();
        params.append('date', dateInput.value);
        if (employeeSelect && employeeSelect.value) {
            params.append('employee_id', employeeSelect.value);
        }
        fetch(`/api/availability?${params.toString()}`)
            .then(r => r.json())
            .then(renderSlots)
            .catch(() => {
                availabilityContainer.innerHTML = '<p class="muted">Unable to load availability right now.</p>';
            });
    };

    if (dateInput) {
        dateInput.addEventListener('change', fetchAvailability);
    }
    if (employeeSelect) {
        employeeSelect.addEventListener('change', fetchAvailability);
    }
    if (calendarEl) {
        renderCalendar();
        prevMonthBtn?.addEventListener('click', () => {
            currentMonth.setMonth(currentMonth.getMonth() - 1);
            renderCalendar();
        });
        nextMonthBtn?.addEventListener('click', () => {
            currentMonth.setMonth(currentMonth.getMonth() + 1);
            renderCalendar();
        });
    }
    syncDepositCopy();
    serviceSelect?.addEventListener('change', syncDepositCopy);
    fetchAvailability();
});
