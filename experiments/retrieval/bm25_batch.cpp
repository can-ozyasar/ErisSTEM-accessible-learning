// Optional local BM25 benchmark core. All data is supplied over stdin.
// Python prepares Turkish tokens and enforces source approval and policy.
#include <algorithm>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

struct Document {
    std::string id;
    int page = 0;
    int length = 0;
    std::unordered_map<std::string, int> terms;
};

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);
    int document_count = 0, query_count = 0, limit = 0;
    if (!(std::cin >> document_count >> query_count >> limit)
        || document_count < 1 || query_count < 1 || limit < 1) return 2;
    std::string line;
    std::getline(std::cin, line);
    std::vector<Document> documents;
    std::unordered_map<std::string, int> document_frequency;
    double total_length = 0.0;
    for (int i = 0; i < document_count; ++i) {
        if (!std::getline(std::cin, line)) return 2;
        std::istringstream row(line);
        std::string page_text, words, token;
        Document document;
        if (!std::getline(row, document.id, '\t')
            || !std::getline(row, page_text, '\t')
            || !std::getline(row, words)) return 2;
        try { document.page = std::stoi(page_text); }
        catch (...) { return 2; }
        std::istringstream stream(words);
        while (stream >> token) {
            ++document.terms[token];
            ++document.length;
        }
        for (const auto& item : document.terms) ++document_frequency[item.first];
        total_length += document.length;
        documents.push_back(std::move(document));
    }
    const double average_length = total_length / document_count;
    if (average_length == 0) return 2;
    std::cout << std::fixed << std::setprecision(3);
    for (int q = 0; q < query_count; ++q) {
        if (!std::getline(std::cin, line)) return 2;
        const auto started = std::chrono::steady_clock::now();
        std::istringstream stream(line);
        std::unordered_set<std::string> query_terms;
        std::string token;
        while (stream >> token) query_terms.insert(token);
        struct Result { double score; int page; std::string id; };
        std::vector<Result> results;
        for (const auto& document : documents) {
            double score = 0.0;
            for (const auto& word : query_terms) {
                auto tf = document.terms.find(word);
                if (tf == document.terms.end()) continue;
                const double df = document_frequency[word];
                const double idf = std::log(1.0 + (document_count - df + 0.5) / (df + 0.5));
                score += idf * tf->second * 2.2 /
                         (tf->second + 1.2 * (0.25 + 0.75 * document.length / average_length));
            }
            if (score > 0) results.push_back({score, document.page, document.id});
        }
        std::sort(results.begin(), results.end(), [](const Result& a, const Result& b) {
            if (a.score != b.score) return a.score > b.score;
            if (a.page != b.page) return a.page < b.page;
            return a.id < b.id;
        });
        const int count = std::min(limit, static_cast<int>(results.size()));
        const auto elapsed = std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::steady_clock::now() - started).count();
        std::cout << count << '\t' << elapsed << '\n';
        for (int i = 0; i < count; ++i)
            std::cout << results[i].id << '\t' << results[i].score << '\n';
    }
    return 0;
}
