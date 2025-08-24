async function searchData() {
    const keyword = document.getElementById('searchInput').value;
    const resultsPre = document.getElementById('resultsPre');

    // Updated GraphQL query to remove 'isInherentDistrict'
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
            sourceFile
        }
    }
    `;

    const variables = { keyword };

    resultsPre.innerHTML = '<span style="color: #007BFF;">Loading...</span>';

    try {
        const response = await fetch('/graphql', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, variables })
        });

        const data = await response.json();

        console.log('GraphQL response:', data);

        document.querySelectorAll('polygon.district-highlight').forEach(el => {
            el.classList.remove('district-highlight');
        });
        document.querySelectorAll('path.district-highlight').forEach(el => {
            el.classList.remove('district-highlight');
        });

        if (data.errors && data.errors.length) {
            resultsPre.textContent = "GraphQL error: " + data.errors.map(e => e.message).join('; ');
        } else if (data.data && data.data.allData && Array.isArray(data.data.allData)) {
            let filteredData = data.data.allData.filter(item =>
            (item.ErststimmenAnzahl > 0) ||
            (item.ZweitstimmenAnzahl > 0)
            );

            filteredData.sort((a, b) => b.ZweitstimmenAnzahl - a.ZweitstimmenAnzahl);

            if (filteredData.length === 0) {
                resultsPre.textContent = "No results found with more than 0 votes.";
            } else {
                resultsPre.textContent = filteredData.map(
                    item => Object.entries(item).map(([k, v]) => `${k}: ${v}`).join('\n')
                ).join('\n\n---\n\n');
            }
        } else if (data.data && data.data.allData === null) {
            resultsPre.textContent = "No results found (null).";
        } else if (data.data) {
            resultsPre.textContent = JSON.stringify(data.data, null, 2);
        } else {
            resultsPre.textContent = "No data found.";
        }
    } catch (error) {
        resultsPre.textContent = `Error: ${error.message}`;
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
