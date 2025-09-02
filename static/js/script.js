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
let deutschlandGeoJSONLayer = null; // New global variable for Germany layer
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

function getColor(d) {
    const colors = [
        '#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231',
        '#911eb4', '#46f0f0', '#f032e6', '#bcf60c', '#fabebe',
        '#008080', '#e6beff', '#9a6324', '#fffac8', '#800000',
        '#aaffc3', '#808000', '#ffd8b1', '#000075', '#808080',
        '#ffffff', '#000000'
    ];
    let hash = 0;
    for (let i = 0; i < d.length; i++) {
        hash = d.charCodeAt(i) + ((hash << 5) - hash);
    }
    const index = Math.abs(hash) % colors.length;
    return colors[index];
}

async function searchData() {
    const keyword = dom.searchInput.value;
    const resultsContainer = dom.resultsPre;
    const parts = keyword.split('>');
    const merkmal = parts[0].trim();
    const threshold = parts.length > 1 ? parseInt(parts[1].trim(), 10) : 0;
    if (parts.length > 1 && isNaN(threshold)) {
        resultsContainer.textContent = "Error: Invalid threshold value. Please enter a number after '>' (e.g., 'AfD > 100').";
        return;
    }
    const query = `
    query GetData($merkmal: String) {
        allData(
            Merkmal: $merkmal
        ) {
            Merkmal
            ErststimmenAnzahl
            ZweitstimmenAnzahl
            districtId
            wahlkreisId
            sourceType
            sourceFile
        }
    }
    `;
    const variables = { merkmal };
    resultsContainer.innerHTML = '<span style="color: #007BFF;">Loading...</span>';
    try {
        const response = await fetch('/graphql', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, variables })
        });
        const data = await response.json();
        let pollingPlaceIdsToShow = [];
        if (data.errors && data.errors.length) {
            resultsContainer.textContent = "GraphQL error: " + data.errors.map(e => e.message).join('; ');
        } else if (data.data && data.data.allData && Array.isArray(data.data.allData)) {
            // First, filter to get only items with a valid 16-digit districtId
            let validDistrictData = data.data.allData.filter(item => {
                return typeof item.districtId === 'string' && /^\d{16}$/.test(item.districtId);
            });
            // Then, apply the threshold filter to the valid data
            let filteredData = validDistrictData.filter(item => {
                const erststimmen = item.ErststimmenAnzahl !== null ? parseInt(item.ErststimmenAnzahl, 10) : 0;
                const zweitstimmen = item.ZweitstimmenAnzahl !== null ? parseInt(item.ZweitstimmenAnzahl, 10) : 0;
                return (erststimmen > threshold || zweitstimmen > threshold);
            });
            filteredData.sort((a, b) => (parseInt(b.ZweitstimmenAnzahl, 10) || 0) - (parseInt(a.ZweitstimmenAnzahl, 10) || 0));
            if (filteredData.length === 0) {
                resultsContainer.textContent = `No results found for '${merkmal}' with more than ${threshold} votes and a valid 16-digit districtId.`;
            } else {
                resultsContainer.innerHTML = '';
                pollingPlaceIdsToShow = filteredData.map(item => item.districtId);
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
            resultsContainer.textContent = `No results found for '${merkmal}' (null).`;
        } else {
            resultsContainer.textContent = `No data found for '${merkmal}'.`;
        }
        showAllPollingPlaceMarkers(pollingPlaceIdsToShow);
    } catch (error) {
        resultsContainer.textContent = `Error: ${error.message}`;
        console.error('Error running GraphQL query:', error);
    }
}

window.highlightDistrict = (districtId) => {
    // Get the actual L.geoJSON layer from the layer group
    const geoJSON = geojsonLayer.getLayers()[0];
    const districtNumber = districtId.replace('wk', '');

    if (geoJSON) {
        geoJSON.eachLayer(function(layer) {
            if (layer.feature.properties.gebietNr === districtNumber) {
                layer.setStyle(highlightStyle);
            } else {
                layer.setStyle(defaultStyle);
            }
        });
    }
};

window.resetHighlight = () => {
    // Get the actual L.geoJSON layer from the layer group
    const geoJSON = geojsonLayer.getLayers()[0];

    if (geoJSON) {
        geoJSON.resetStyle();
    }
};

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
    const fetchPromises = pollingPlaceIds.map(id => {
        const filePath = window.STATIC_PATHS.wahllokalData + `${id}.csv`;
        return fetch(filePath)
        .then(response => {
            if (!response.ok) {
                throw new Error(`File not found or network error: ${filePath}`);
            }
            return response.text();
        })
        .then(csvText => {
            const lines = csvText.trim().split('\n');
            if (lines.length > 1) {
                const values = lines[1].split(',').map(v => v.trim());
                const locationData = {
                    id: id,
                    name: values[0],
                    lat: parseFloat(values[1]),
              lon: parseFloat(values[2])
                };
                return !isNaN(locationData.lat) && !isNaN(locationData.lon) ? locationData : null;
            }
            return null;
        })
        .catch(error => {
            console.error(`Error processing file ${filePath}:`, error);
            return null;
        });
    });
    const results = await Promise.all(fetchPromises);
    allPollingPlaceData = results.filter(data => data !== null);
    showAllPollingPlaceMarkers();
}

function showAllPollingPlaceMarkers(idsToDisplay = null) {
    pollingPlaceMarkers.clearLayers();
    const customIcon = L.icon({
        iconUrl: window.STATIC_PATHS.wahllokalPin,
        iconSize: [21, 21],
        iconAnchor: [10.5, 21],
        popupAnchor: [0, -25]
    });
    let dataToUse = allPollingPlaceData;
    if (idsToDisplay && idsToDisplay.length > 0) {
        const idsSet = new Set(idsToDisplay);
        dataToUse = allPollingPlaceData.filter(data => idsSet.has(data.id));
    }
    dataToUse.forEach(data => {
        const marker = L.marker([data.lat, data.lon], { icon: customIcon });
        const initialPopupContent = `<b>${data.name}</b><br>ID: ${data.id}<br><br>Loading data...`;
        marker.bindPopup(initialPopupContent);
        marker.on('click', async function () {
            const query = `
            query GetPollingPlaceData($districtId: String!) {
                allData(districtId: $districtId) {
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
            const variables = { districtId: data.id };
            try {
                const response = await fetch('/graphql', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query, variables })
                });
                const graphqlData = await response.json();
                let popupHtml = `<b>${data.name}</b><br>ID: ${data.id}<br><br>`;
                if (graphqlData.errors && graphqlData.errors.length) {
                    popupHtml += "Error: " + graphqlData.errors[0].message;
                } else if (graphqlData.data && graphqlData.data.allData) {
                    const allData = graphqlData.data.allData;
                    let tableContent = `
                    <style>
                    .popup-table { width: 100%; border-collapse: collapse; }
                    .popup-table th, .popup-table td { border: 1px solid #ddd; padding: 4px; text-align: left; font-size: 10px; }
                    .popup-table th { background-color: #f2f2f2; }
                    </style>
                    <table class="popup-table">
                    <thead>
                    <tr>
                    <th>Merkmal</th>
                    <th>Erststimmen</th>
                    <th>Zweitstimmen</th>
                    </tr>
                    </thead>
                    <tbody>
                    `;
                    allData.forEach(item => {
                        const erststimmen = item.ErststimmenAnzahl !== null ? item.ErststimmenAnzahl : 'N/A';
                        const zweitstimmen = item.ZweitstimmenAnzahl !== null ? item.ZweitstimmenAnzahl : 'N/A';
                        if (erststimmen !== 0 || zweitstimmen !== 0) {
                            tableContent += `
                            <tr>
                            <td>${item.Merkmal}</td>
                            <td>${erststimmen}</td>
                            <td>${zweitstimmen}</td>
                            </tr>
                            `;
                        }
                    });
                    tableContent += `
                    </tbody>
                    </table>
                    `;
                    popupHtml += tableContent;
                }
                this.setPopupContent(popupHtml);
            } catch (error) {
                console.error('GraphQL query failed:', error);
                this.setPopupContent(`<b>${data.name}</b><br>ID: ${data.id}<br><br>Error fetching data.`);
            }
        });
        pollingPlaceMarkers.addLayer(marker);
    });
}

async function loadGeoJSON() {
    // GraphQL query to get data for a specific main electoral district
    const mainDistrictQuery = `
    query GetWahlkreisData($wahlkreisId: String!) {
        allData(wahlkreisId: $wahlkreisId) {
            Merkmal
            ErststimmenAnzahl
            ZweitstimmenAnzahl
        }
    }
    `;

    try {
        const response = await fetch(window.STATIC_PATHS.geojson);
        const data = await response.json();
        const geojsonData = data.geoJSON;

        // Clear any existing layers before adding new ones
        geojsonLayer.clearLayers();

        // Create the L.geoJSON layer and store it in a local variable
        const newGeojsonLayer = L.geoJSON(geojsonData, {
            renderer: myRenderer,
            style: function(feature) {
                return defaultStyle;
            },
            onEachFeature: function(feature, layer) {
                if (feature.properties && feature.properties.name && feature.properties.gebietNr) {
                    const wahlkreisId = `wk${feature.properties.gebietNr}`; // Construct the ID
                    layer.bindPopup('Loading data...'); // Initial loading state

                    layer.on('popupopen', async function () {
                        const variables = { wahlkreisId };
                        try {
                            const response = await fetch('/graphql', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ query: mainDistrictQuery, variables })
                            });
                            const graphqlData = await response.json();

                            let popupHtml = `<b>${feature.properties.name}</b><br>Wahlkreis: ${wahlkreisId}<br><br>`;

                            if (graphqlData.errors) {
                                popupHtml += "Error: " + graphqlData.errors[0].message;
                            } else if (graphqlData.data && graphqlData.data.allData) {
                                const allData = graphqlData.data.allData;

                                // Aggregate data
                                const aggregatedData = {};
                                allData.forEach(item => {
                                    const merkmal = item.Merkmal;
                                    const erststimmen = parseInt(item.ErststimmenAnzahl, 10) || 0;
                                    const zweitstimmen = parseInt(item.ZweitstimmenAnzahl, 10) || 0;

                                    if (!aggregatedData[merkmal]) {
                                        aggregatedData[merkmal] = { ErststimmenAnzahl: 0, ZweitstimmenAnzahl: 0 };
                                    }
                                    aggregatedData[merkmal].ErststimmenAnzahl += erststimmen;
                                    aggregatedData[merkmal].ZweitstimmenAnzahl += zweitstimmen;
                                });

                                let tableContent = `
                                <style>
                                .popup-table { width: 100%; border-collapse: collapse; }
                                .popup-table th, .popup-table td { border: 1px solid #ddd; padding: 4px; text-align: left; font-size: 10px; }
                                .popup-table th { background-color: #f2f2f2; }
                                </style>
                                <table class="popup-table">
                                <thead>
                                <tr>
                                <th>Merkmal</th>
                                <th>Erststimmen</th>
                                <th>Zweitstimmen</th>
                                </tr>
                                </thead>
                                <tbody>
                                `;

                                Object.entries(aggregatedData).forEach(([merkmal, votes]) => {
                                    if (votes.ErststimmenAnzahl > 0 || votes.ZweitstimmenAnzahl > 0) {
                                        tableContent += `
                                        <tr>
                                        <td>${merkmal}</td>
                                        <td>${votes.ErststimmenAnzahl}</td>
                                        <td>${votes.ZweitstimmenAnzahl}</td>
                                        </tr>
                                        `;
                                    }
                                });

                                tableContent += `</tbody></table>`;
                                popupHtml += tableContent;
                            } else {
                                popupHtml += "No data found for this district.";
                            }

                            this.setPopupContent(popupHtml);

                        } catch (error) {
                            console.error('GraphQL query failed:', error);
                            this.setPopupContent(`<b>${feature.properties.name}</b><br>Error fetching data.`);
                        }
                    });
                }
            }
        });

        // Add the new L.geoJSON layer to your L.layerGroup
        newGeojsonLayer.addTo(geojsonLayer);

        // Add the layer group to the map if you want it to be visible by default
        geojsonLayer.addTo(map);

        // Now, call getBounds() on the correct layer instance
        if (newGeojsonLayer.getLayers().length > 0) {
            map.fitBounds(newGeojsonLayer.getBounds());
        }
    } catch (error) {
        console.error('Error loading GeoJSON:', error);
    }
}

async function loadDeutschlandGeoJSON() {
    try {
        const response = await fetch('static/data/deutschland_geo.json');
        const data = await response.json();

        // Check if CRS is defined and if it's not WGS84
        if (data.crs && data.crs.properties && data.crs.properties.name === "urn:ogc:def:crs:EPSG::25832") {
            // Define the projection for EPSG:25832
            const projDef = '+proj=utm +zone=32 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs';
            const proj = new L.Proj.CRS('EPSG:25832', projDef);

            const germanyLayer = L.Proj.geoJson(data, {
                renderer: myRenderer,
                style: {
                    color: '#555',
                    weight: 1,
                    opacity: 0.8,
                    fillColor: '#888',
                    fillOpacity: 0.2
                },
                onEachFeature: function(feature, layer) {
                    if (feature.properties && feature.properties.name) {
                        layer.bindPopup(feature.properties.name);
                    }
                }
            });
            germanyLayer.addTo(deutschlandGeoJSONLayer);
        } else {
            console.error('The GeoJSON file is not in EPSG:25832 projection or the CRS is missing.');
        }

    } catch (error) {
        console.error('Error loading Germany GeoJSON:', error);
    }
}

function initMapAndData() {
    myRenderer = L.canvas();
    map = L.map('osm', {
        renderer: myRenderer
    }).setView([52.52, 13.12], 7);
    const osmStandard = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    });
    const openTopoMap = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
        maxZoom: 17,
        attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)'
    });
    const esriWorldImagery = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
    });
    const cartoDarkMatter = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 19
    });
    osmStandard.addTo(map);
    const baseLayers = {
        "OpenStreetMap": osmStandard,
        "Topography": openTopoMap,
        "Esri Sat": esriWorldImagery,
        "Night Map": cartoDarkMatter
    };
    pollingPlaceMarkers = L.layerGroup();
    geojsonLayer = L.layerGroup();
    deutschlandGeoJSONLayer = L.layerGroup(); // Initialize the new layer group
    const overlayLayers = {
        "Polling Places": pollingPlaceMarkers,
        "Polling Districts": geojsonLayer,
        "Germany Border": deutschlandGeoJSONLayer // Add the new layer to the control
    };
    L.control.layers(baseLayers, overlayLayers).addTo(map);
    // Add the polling place markers layer to the map on initialization.
    pollingPlaceMarkers.addTo(map);
    loadGeoJSON();
    loadDeutschlandGeoJSON(); // Call the new function
    loadAllPollingPlaceData();
}

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

window.searchData = searchData;
