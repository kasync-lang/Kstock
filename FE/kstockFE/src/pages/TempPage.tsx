

function TempPage() {
    return (
        <div>
            <h1>Temp Page</h1>
            <p>This page is only for testing purposes.</p>
            <p>If you are seeing this page, it means you are not logged in.</p>
            <button onClick={() => window.history.back()}>Go back</button>
        </div>
    );
}

export default TempPage;