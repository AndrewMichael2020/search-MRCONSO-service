#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <string>
#include <vector>
#include <algorithm>
#include <memory>

namespace py = pybind11;

// Levenshtein distance implementation
int levenshtein(const std::string& s1, const std::string& s2) {
    const size_t m = s1.size();
    const size_t n = s2.size();
    
    if (m == 0) return n;
    if (n == 0) return m;
    
    std::vector<std::vector<int>> dp(m + 1, std::vector<int>(n + 1));
    
    for (size_t i = 0; i <= m; ++i) dp[i][0] = i;
    for (size_t j = 0; j <= n; ++j) dp[0][j] = j;
    
    for (size_t i = 1; i <= m; ++i) {
        for (size_t j = 1; j <= n; ++j) {
            int cost = (s1[i-1] == s2[j-1]) ? 0 : 1;
            dp[i][j] = std::min({
                dp[i-1][j] + 1,      // deletion
                dp[i][j-1] + 1,      // insertion
                dp[i-1][j-1] + cost  // substitution
            });
        }
    }
    
    return dp[m][n];
}

// BK-tree node structure
struct BKNode {
    std::string term;
    std::vector<std::pair<int, std::shared_ptr<BKNode>>> children;
    
    BKNode(const std::string& t) : term(t) {}
};

// BK-tree implementation
class BKTree {
private:
    std::shared_ptr<BKNode> root;
    
    void insertHelper(std::shared_ptr<BKNode>& node, const std::string& term) {
        if (!node) {
            node = std::make_shared<BKNode>(term);
            return;
        }
        
        int dist = levenshtein(node->term, term);
        if (dist == 0) return; // duplicate
        
        // Find child with this distance
        for (auto& child : node->children) {
            if (child.first == dist) {
                insertHelper(child.second, term);
                return;
            }
        }
        
        // No child with this distance, create new
        auto newNode = std::make_shared<BKNode>(term);
        node->children.push_back({dist, newNode});
    }
    
    void searchHelper(const std::shared_ptr<BKNode>& node, const std::string& query, 
                     int maxDist, std::vector<std::pair<std::string, int>>& results) const {
        if (!node) return;
        
        int dist = levenshtein(node->term, query);
        if (dist <= maxDist) {
            results.push_back({node->term, dist});
        }
        
        // Prune search by distance band
        int minDist = dist - maxDist;
        int maxDistEdge = dist + maxDist;
        
        for (const auto& child : node->children) {
            if (child.first >= minDist && child.first <= maxDistEdge) {
                searchHelper(child.second, query, maxDist, results);
            }
        }
    }
    
public:
    BKTree() : root(nullptr) {}
    
    void insert(const std::string& term) {
        insertHelper(root, term);
    }
    
    std::vector<std::pair<std::string, int>> search(const std::string& query, int maxDist) const {
        std::vector<std::pair<std::string, int>> results;
        searchHelper(root, query, maxDist, results);
        
        // Sort by distance, then alphabetically
        std::sort(results.begin(), results.end(), 
            [](const std::pair<std::string, int>& a, const std::pair<std::string, int>& b) {
                if (a.second != b.second) return a.second < b.second;
                return a.first < b.first;
            });
        
        return results;
    }
};

PYBIND11_MODULE(cppmatch, m) {
    m.doc() = "BK-tree fuzzy string matching with pybind11";
    
    m.def("levenshtein", &levenshtein, 
          "Calculate Levenshtein distance between two strings",
          py::arg("s1"), py::arg("s2"));
    
    py::class_<BKTree>(m, "BKTree")
        .def(py::init<>())
        .def("insert", &BKTree::insert, 
             "Insert a term into the BK-tree",
             py::arg("term"))
        .def("search", &BKTree::search, 
             "Search for terms within maxDist of query",
             py::arg("query"), py::arg("maxdist"));
}
