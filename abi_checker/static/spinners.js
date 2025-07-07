'use strict';

const ws_url = document.getElementById('ws_url').href;
const socket = new WebSocket(ws_url);

socket.onmessage = function (event) {
    const msg_run = event.data;
    const elem = document.querySelector(`updating-spinner[data-run="${msg_run}"]`);
    if (elem) {
        (async () => {
            var outerHTML = '⁉️';
            try {
                const response = await fetch(elem.getAttribute('href'));
                if (response.status == 200) {
                    outerHTML = await response.text();
                }
            } finally {
                elem.classList.remove('spinning');
                elem.outerHTML = outerHTML;
            }
        })();
    }
}

socket.onclose = function (event) {
    console.log('connection lost');
    for (const elem of document.getElementsByTagName('updating-spinner')) {
        elem.outerHTML = '⁉️';
    }
}

socket.onopen = function (event) {
    class UpdatingSpinner extends HTMLElement {
        connectedCallback() {
            this.classList.add('spinning');
            const data_run = this.getAttribute('data-run');
            socket.send(data_run);
        }
    }

    customElements.define('updating-spinner', UpdatingSpinner);
}
