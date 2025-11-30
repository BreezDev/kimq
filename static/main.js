document.addEventListener('DOMContentLoaded', () => {
    const availabilityContainer = document.querySelector('#availability');
    const dateInput = document.querySelector('#date');
    const employeeSelect = document.querySelector('#employee_id');

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
        fetchAvailability();
    }
    if (employeeSelect) {
        employeeSelect.addEventListener('change', fetchAvailability);
    }
});
