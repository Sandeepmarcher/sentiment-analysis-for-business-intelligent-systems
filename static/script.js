document.addEventListener("DOMContentLoaded", function () {
    const analyzeBtn = document.getElementById("analyze-btn");
    const productSelect = document.getElementById("product");
    const brandSelect = document.getElementById("brand");
    const priceElement = document.getElementById("price");
    const ratingElement = document.getElementById("avg-rating");
    const chartContainer = document.getElementById("chart");
    const reviewsContainer = document.getElementById("reviews");
    const generateBtn = document.getElementById("generate-btn");
    const reviewInput = document.getElementById("review-input");
    const generatedReview = document.getElementById("generated-review");

    if (!analyzeBtn || !productSelect || !brandSelect || !generateBtn) {
        console.error("One or more elements not found!");
        return;
    }

    analyzeBtn.addEventListener("click", function () {
        const product = productSelect.value;
        const brand = brandSelect.value;

        if (!product || !brand) {
            alert("Please select both product and brand.");
            return;
        }

        priceElement.textContent = "Fetching details...";
        ratingElement.textContent = "";
        reviewsContainer.innerHTML = `<p>Loading reviews...</p>`;
        chartContainer.innerHTML = "";

        fetch(`/api//analyze?product=${encodeURIComponent(product)}&brand=${encodeURIComponent(brand)}`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    reviewsContainer.innerHTML = `<p class="error">${data.error}</p>`;
                    return;
                }

                priceElement.textContent = `Price: $${data.price}`;
                ratingElement.textContent = `Average Rating: ${data.avg_rating}`;

                reviewsContainer.innerHTML = `
                    <h3>Sample User Reviews</h3>
                    <p class="p"><strong>Positive:</strong> ${data.reviews.Positive.join("<br>")}</p>
                    <p class="p"><strong>Neutral:</strong> ${data.reviews.Neutral.join("<br>")}</p>
                    <p class="p"><strong>Negative:</strong> ${data.reviews.Negative.join("<br>")}</p>
                `;

                if (data.meta_ai_summary) {
                    reviewsContainer.innerHTML += `
                        <h3>AI Insights</h3>
                        <p>${data.meta_ai_summary}</p>
                    `;
                }

                if (data.charts && data.charts.bar) {
                    Plotly.newPlot("chart", JSON.parse(data.charts.bar));
                }
            })
            .catch(error => {
                console.error("Error:", error);
                reviewsContainer.innerHTML = `<p class="error">Failed to load data.</p>`;
            });
    });

    generateBtn.addEventListener("click", function () {
        const productName = reviewInput.value.trim();
    
        if (!productName) {
            alert("Please enter a product name.");
            return;
        }

        generatedReview.innerHTML = `<p>Generating review...</p>`;

        fetch("/api/generate_review", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ product_name: productName })
        })
        .then(response => response.json())
        .then(data => {
            console.log("AI Review Response:", data);
            generatedReview.innerText = data.message || "No review found.";
        })
        .catch(error => console.error("Error:", error));
    });

    
});
