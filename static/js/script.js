// Import necessary components and utilities
import { ThemeToggle } from './components/ThemeToggle.js';
import { getDOMElements } from './utils/domElements.js';

// Get DOM elements for the script
const dom = getDOMElements();

// Initialize the theme toggle
new ThemeToggle();

// Global variables for map and data
let allPollingPlaceData = [];
let geojsonLayer = null;
let pollingPlaceMarkers = null;
let map = null;
let myRenderer = null;

const defaultStyle = {
    color: '#007BFF',
    weight: 1,
    opacity: 1,
    fillColor: '#007BFF',
    fillOpacity: 0.07
};

const highlightStyle = {
    color: 'black',
    weight: 3,
    opacity: 1,
    fillColor: '#FFD700',
    fillOpacity: 0.7
};

// --- CORE FUNCTIONS (NO JINJA) ---
// Function to handle GraphQL search
async function searchData() {
    const keyword = dom.searchInput.value;
    const resultsContainer = dom.resultsPre;

    const query = `
    query GetData($keyword: String) {
        allData(
            Merkmal: $keyword
        ) {
            Merkmal
            ErststimmenAnzahl
            ErststimmenAnteil
            ErststimmenGewinn
            ZweitstimmenAnzahl
            ZweitstimmenAnteil
            ZweitstimmenGewinn
            districtId
            wahlkreisId
            sourceType
            sourceFile
        }
    }
    `;

    const variables = { keyword };

    resultsContainer.innerHTML = '<span style="color: #007BFF;">Loading...</span>';

    try {
        const response = await fetch('/graphql', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, variables })
        });

        const data = await response.json();
        console.log('GraphQL response:', data);

        let pollingPlaceIdsToShow = [];

        if (data.errors && data.errors.length) {
            resultsContainer.textContent = "GraphQL error: " + data.errors.map(e => e.message).join('; ');
            showAllPollingPlaceMarkers();
        } else if (data.data && data.data.allData && Array.isArray(data.data.allData)) {
            let filteredData = data.data.allData.filter(item =>
            (item.ErststimmenAnzahl > 0) || (item.ZweitstimmenAnzahl > 0)
            );

            filteredData.sort((a, b) => b.ZweitstimmenAnzahl - a.ZweitstimmenAnzahl);

            if (filteredData.length === 0) {
                resultsContainer.textContent = "No results found with more than 0 votes.";
                pollingPlaceMarkers.clearLayers();
            } else {
                resultsContainer.innerHTML = '';

                pollingPlaceIdsToShow = filteredData
                .map(item => item.districtId)
                .filter(districtId => /^\d{16}$/.test(districtId));

                filteredData.forEach(item => {
                    const resultDiv = document.createElement('div');
                    resultDiv.classList.add('result-item');
                    resultDiv.setAttribute('data-district-id', item.wahlkreisId);
                    resultDiv.onmouseover = () => { window.highlightDistrict(item.wahlkreisId); };
                    resultDiv.onmouseout = () => { window.resetHighlight(); };

                    const content = Object.entries(item)
                    .map(([k, v]) => `<strong>${k}:</strong> ${v}`)
                    .join('<br>');

                    resultDiv.innerHTML = content;
                    resultsContainer.appendChild(resultDiv);
                });
            }
        } else if (data.data && data.data.allData === null) {
            resultsContainer.textContent = "No results found (null).";
            pollingPlaceMarkers.clearLayers();
        } else {
            resultsContainer.textContent = "No data found.";
            pollingPlaceMarkers.clearLayers();
        }
        filterPollingPlaceMarkers(pollingPlaceIdsToShow);
    } catch (error) {
        resultsContainer.textContent = `Error: ${error.message}`;
        console.error('Error running GraphQL query:', error);
        showAllPollingPlaceMarkers();
    }
}

// Functions to highlight and reset the district on the map
window.highlightDistrict = (districtId) => {
    const districtNumber = districtId.replace('wk', '');
    if (geojsonLayer) {
        geojsonLayer.eachLayer(function(layer) {
            if (layer.feature.properties.gebietNr === districtNumber) {
                layer.setStyle(highlightStyle);
            } else {
                layer.setStyle(defaultStyle);
            }
        });
    }
};

window.resetHighlight = () => {
    if (geojsonLayer) {
        geojsonLayer.resetStyle();
    }
};

// --- MAP AND MARKER MANAGEMENT FUNCTIONS ---
async function loadAllPollingPlaceData() {
    let pollingPlaceIds = [];
    try {
        const response = await fetch('/api/polling-places');
        if (response.ok) {
            pollingPlaceIds = await response.json();
        } else {
            console.error("Failed to fetch polling place list:", response.status, await response.text());
            return;
        }
    } catch (error) {
        console.error("Network error fetching polling place list:", error);
        return;
    }

    for (const id of pollingPlaceIds) {
        // Use the global variable
        const filePath = window.STATIC_PATHS.wahllokalData + `${id}.csv`;
        try {
            const response = await fetch(filePath);
            if (!response.ok) {
                throw new Error(`File not found or network error: ${filePath}`);
            }
            const csvText = await response.text();
            const lines = csvText.trim().split('\n');
            if (lines.length > 1) {
                const values = lines[1].split(',').map(v => v.trim());
                const locationData = {
                    id: id,
                    name: values[0],
                    lat: parseFloat(values[1]),
                    lon: parseFloat(values[2])
                };
                if (!isNaN(locationData.lat) && !isNaN(locationData.lon)) {
                    allPollingPlaceData.push(locationData);
                }
            }
        } catch (error) {
            console.error(`Error processing file ${filePath}:`, error);
        }
    }
    showAllPollingPlaceMarkers();
}

function filterPollingPlaceMarkers(idsToDisplay) {
    pollingPlaceMarkers.clearLayers();
    const customIcon = L.icon({
        // Use the global variable
        iconUrl: window.STATIC_PATHS.wahllokalPin,
        iconSize: [32, 32],
        iconAnchor: [16, 32],
        popupAnchor: [0, -25]
    });
    const idsSet = new Set(idsToDisplay);
    allPollingPlaceData.forEach(data => {
        if (idsSet.has(data.id)) {
            const marker = L.marker([data.lat, data.lon], { icon: customIcon });
            const popupContent = `<b>${data.name}</b><br>ID: ${data.id}`;
            marker.bindPopup(popupContent);
            pollingPlaceMarkers.addLayer(marker);
        }
    });
}

function showAllPollingPlaceMarkers() {
    pollingPlaceMarkers.clearLayers();
    const customIcon = L.icon({
        // Use the global variable
        iconUrl: window.STATIC_PATHS.wahllokalPin,
        iconSize: [32, 32],
        iconAnchor: [16, 32],
        popupAnchor: [0, -25]
    });
    allPollingPlaceData.forEach(data => {
        const marker = L.marker([data.lat, data.lon], { icon: customIcon });
        const popupContent = `<b>${data.name}</b><br>ID: ${data.id}`;
        marker.bindPopup(popupContent);
        pollingPlaceMarkers.addLayer(marker);
    });
}

// Function to load and add GeoJSON data to the map
async function loadGeoJSON() {
    try {
        // Use the global variable
        const response = await fetch(window.STATIC_PATHS.geojson);
        const data = await response.json();
        const geojsonData = data.geoJSON;
        if (geojsonLayer) {
            map.removeLayer(geojsonLayer);
        }
        geojsonLayer = L.geoJSON(geojsonData, {
            renderer: myRenderer,
            style: function(feature) {
                return defaultStyle;
            },
            onEachFeature: function(feature, layer) {
                if (feature.properties && feature.properties.name) {
                    layer.bindPopup(feature.properties.name);
                }
            }
        }).addTo(map);
    } catch (error) {
        console.error('Error loading GeoJSON:', error);
    }
}

// --- INITIALIZATION ---
function initMapAndData() {
    // myRenderer is now a global variable, so we just assign to it
    myRenderer = L.canvas();
    map = L.map('osm', {
        renderer: myRenderer
    }).setView([52.52, 13.12], 7);
    const osmStandard = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' });
    const openTopoMap = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', { maxZoom: 17, attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)' });
    const cyclOSM = L.tileLayer('https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png', { maxZoom: 20, attribution: '<a href="https://github.com/cyclosm/cyclosm-cartocss-style/releases" title="CyclOSM - OpenStreetMap Cycle Map">CyclOSM</a> | &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' });
    const esriWorldImagery = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community' });
    cyclOSM.addTo(map);
    const baseLayers = { "OpenStreetMap": osmStandard, "Topography": openTopoMap, "Bicycle Map (CyclOSM)": cyclOSM, "Esri Sat": esriWorldImagery };
    L.control.layers(baseLayers).addTo(map);
    pollingPlaceMarkers = L.layerGroup().addTo(map);

    // Call initial loading functions
    loadGeoJSON();
    loadAllPollingPlaceData();
}

// Attach event listeners and expose the function globally
document.addEventListener('DOMContentLoaded', () => {
    initMapAndData();
    const input = dom.searchInput;
    const button = dom.searchButton;
    if (input) {
        input.addEventListener('keydown', e => {
            if (e.key === 'Enter') searchData();
        });
    }
    if (button) button.addEventListener('click', searchData);
});

// IMPORTANT: Expose the searchData function to the global scope
window.searchData = searchData;
