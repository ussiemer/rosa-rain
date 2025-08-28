export function getDOMElements() {
    return {
        body: document.body,
        themeToggleButton: document.getElementById('theme-toggle-button'),
        searchInput: document.getElementById('searchInput'),
        searchButton: document.getElementById('searchButton'),
        resultsPre: document.getElementById('resultsPre'),
        // Add any other elements you need to access here
    };
}
