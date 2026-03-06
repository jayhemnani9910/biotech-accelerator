/**
 * Terminal typing effect for Biotech Research Accelerator demo
 */

class Terminal {
    constructor(options = {}) {
        this.queryElement = document.getElementById('query-text');
        this.outputElement = document.getElementById('terminal-output');
        this.cursorElement = document.querySelector('.cursor');
        this.typingSpeed = options.typingSpeed || 50;
        this.lineDelay = options.lineDelay || 200;
    }

    /**
     * Type out text character by character
     */
    async typeText(text, element = this.queryElement) {
        element.textContent = '';
        this.showCursor();

        for (let i = 0; i < text.length; i++) {
            element.textContent += text[i];
            await this.sleep(this.typingSpeed);
        }
    }

    /**
     * Add output line to terminal
     */
    addOutputLine(text, className = '') {
        const line = document.createElement('div');
        line.className = `output-line ${className}`;
        line.textContent = text;
        this.outputElement.appendChild(line);

        // Trigger animation
        requestAnimationFrame(() => {
            line.style.animationDelay = '0s';
        });

        return line;
    }

    /**
     * Add multiple output lines with delays
     */
    async addOutputLines(lines) {
        for (const lineData of lines) {
            const text = typeof lineData === 'string' ? lineData : lineData.text;
            const className = typeof lineData === 'string' ? '' : lineData.class || '';

            this.addOutputLine(text, className);
            await this.sleep(this.lineDelay);
        }
    }

    /**
     * Clear terminal output
     */
    clearOutput() {
        this.outputElement.innerHTML = '';
    }

    /**
     * Clear query text
     */
    clearQuery() {
        this.queryElement.textContent = '';
    }

    /**
     * Reset terminal to initial state
     */
    reset() {
        this.clearQuery();
        this.clearOutput();
        this.showCursor();
    }

    /**
     * Show cursor
     */
    showCursor() {
        this.cursorElement.classList.remove('hidden');
    }

    /**
     * Hide cursor
     */
    hideCursor() {
        this.cursorElement.classList.add('hidden');
    }

    /**
     * Add a loading spinner line
     */
    addSpinner(text) {
        const line = document.createElement('div');
        line.className = 'output-line';
        line.innerHTML = `<span class="spinner"></span> ${text}`;
        this.outputElement.appendChild(line);
        return line;
    }

    /**
     * Remove a specific line
     */
    removeLine(line) {
        if (line && line.parentNode) {
            line.parentNode.removeChild(line);
        }
    }

    /**
     * Sleep utility
     */
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Terminal;
}
