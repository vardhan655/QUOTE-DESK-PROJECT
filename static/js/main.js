/**
 * Quote Desk - Client-side Utilities & Live Calculators
 */

// Modal Controls
function openCreateModal() {
    const modal = document.getElementById('createRfqModal');
    if (modal) {
        modal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
        const input = modal.querySelector('input[name="part_number"]');
        if (input) input.focus();
    }
}

function closeCreateModal() {
    const modal = document.getElementById('createRfqModal');
    if (modal) {
        modal.classList.add('hidden');
        document.body.style.overflow = '';
    }
}

// Close modal on Escape key press
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
        closeCreateModal();
    }
});

// Format Indian Rupee currency
function formatINR(amount) {
    if (isNaN(amount)) return '₹ 0.00';
    return '₹ ' + Number(amount).toLocaleString('en-IN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

// Format Date YYYY-MM-DD to readable
function formatDateStr(dateObj) {
    return dateObj.toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    });
}

// Initialize Live Quote Calculator on RFQ Detail Page
document.addEventListener('DOMContentLoaded', function () {
    const unitPriceInput = document.getElementById('quoteUnitPrice');
    const leadTimeInput = document.getElementById('quoteLeadTime');
    const totalPriceDisplay = document.getElementById('liveTotalPrice');
    const arrivalDateDisplay = document.getElementById('liveArrivalDate');
    const deadlineNotice = document.getElementById('liveDeadlineNotice');

    if (!unitPriceInput || !leadTimeInput || !window.RFQ_DATA) {
        return;
    }

    const { quantity, neededBy, today } = window.RFQ_DATA;
    const neededByDate = new Date(neededBy + 'T00:00:00');
    const refTodayDate = new Date(today + 'T00:00:00');

    function updateLiveCalculation() {
        const unitPrice = parseFloat(unitPriceInput.value) || 0;
        const leadDays = parseInt(leadTimeInput.value, 10);

        // 1. Calculate and display total price
        const total = unitPrice * quantity;
        totalPriceDisplay.textContent = formatINR(total);

        // 2. Calculate and display estimated arrival date
        if (!isNaN(leadDays) && leadDays >= 0) {
            const arrivalDate = new Date(refTodayDate);
            arrivalDate.setDate(arrivalDate.getDate() + leadDays);
            arrivalDateDisplay.textContent = formatDateStr(arrivalDate);

            // Compare with needed_by
            deadlineNotice.classList.remove('hidden');
            if (arrivalDate <= neededByDate) {
                deadlineNotice.className = 'text-[11px] pt-1 border-t border-slate-200 font-medium text-emerald-600';
                deadlineNotice.innerHTML = '✓ Estimated to arrive on or before deadline.';
            } else {
                const diffTime = Math.abs(arrivalDate - neededByDate);
                const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
                deadlineNotice.className = 'text-[11px] pt-1 border-t border-slate-200 font-medium text-rose-600';
                deadlineNotice.innerHTML = `⚠️ Arrives ${diffDays} day(s) after needed_by deadline. This quote will be disqualified!`;
            }
        } else {
            arrivalDateDisplay.textContent = '—';
            deadlineNotice.classList.add('hidden');
        }
    }

    unitPriceInput.addEventListener('input', updateLiveCalculation);
    leadTimeInput.addEventListener('input', updateLiveCalculation);
});
