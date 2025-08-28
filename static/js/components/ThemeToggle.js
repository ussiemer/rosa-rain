import { getDOMElements } from '../utils/domElements.js';

export class ThemeToggle {
    constructor() {
        this.dom = getDOMElements();
        this.init();
    }

    init() {
        this.setInitialTheme();
        if (this.dom.themeToggleButton) {
            this.dom.themeToggleButton.addEventListener('click', () => this.toggleTheme());
        }
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', event => {
            if (!localStorage.getItem('theme')) {
                this.applyTheme(event.matches);
            }
        });
    }

    applyTheme(isDarkMode) {
        if (isDarkMode) {
            this.dom.body.classList.add('dark-theme');
            localStorage.setItem('theme', 'dark');
        } else {
            this.dom.body.classList.remove('dark-theme');
            localStorage.setItem('theme', 'light');
        }
        console.log(`Theme applied: ${isDarkMode ? 'dark' : 'light'}`);
    }

    setInitialTheme() {
        const storedTheme = localStorage.getItem('theme');
        if (storedTheme) {
            this.applyTheme(storedTheme === 'dark');
        } else {
            const prefersDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches;
            this.applyTheme(prefersDarkMode);
        }
    }

    toggleTheme() {
        const isCurrentlyDark = this.dom.body.classList.contains('dark-theme');
        this.applyTheme(!isCurrentlyDark);
    }
}
