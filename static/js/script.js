async function searchData() {
    const keyword = document.getElementById('searchInput').value;
    const resultsContainer = document.getElementById('resultsPre');

    // GraphQL query
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

        if (data.errors && data.errors.length) {
            resultsContainer.textContent = "GraphQL error: " + data.errors.map(e => e.message).join('; ');
        } else if (data.data && data.data.allData && Array.isArray(data.data.allData)) {
            let filteredData = data.data.allData.filter(item =>
            (item.ErststimmenAnzahl > 0) || (item.ZweitstimmenAnzahl > 0)
            );

            filteredData.sort((a, b) => b.ZweitstimmenAnzahl - a.ZweitstimmenAnzahl);

            if (filteredData.length === 0) {
                resultsContainer.textContent = "No results found with more than 0 votes.";
            } else {
                // Clear previous results
                resultsContainer.innerHTML = '';

                filteredData.forEach(item => {
                    const resultDiv = document.createElement('div');
                    resultDiv.classList.add('result-item');

                    // Use the wahlkreisId for the highlighting
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
        } else {
            resultsContainer.textContent = "No data found.";
        }
    } catch (error) {
        resultsContainer.textContent = `Error: ${error.message}`;
        console.error('Error running GraphQL query:', error);
    }
}

window.onload = () => {
    const input = document.getElementById('searchInput');
    if (input) input.value = '';
    searchData();
};

document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('searchInput');
    const button = document.getElementById('searchButton');
    if (input) {
        input.addEventListener('keydown', e => {
            if (e.key === 'Enter') searchData();
        });
    }
    if (button) button.addEventListener('click', searchData);
});
