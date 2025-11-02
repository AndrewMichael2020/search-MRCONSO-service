#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <algorithm>
#include <memory>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

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
    
    py::list toSerializableImpl() const {
        py::list nodes;
        if (!root) {
            return nodes;
        }

        std::vector<std::shared_ptr<BKNode>> queue;
        queue.push_back(root);
        std::unordered_map<BKNode*, std::size_t> index;
        index[root.get()] = 0;

        for (std::size_t i = 0; i < queue.size(); ++i) {
            const auto& node = queue[i];
            py::list childList;
            for (const auto& child : node->children) {
                const auto& childPtr = child.second;
                auto it = index.find(childPtr.get());
                std::size_t childIndex;
                if (it == index.end()) {
                    childIndex = queue.size();
                    queue.push_back(childPtr);
                    index[childPtr.get()] = childIndex;
                } else {
                    childIndex = it->second;
                }
                childList.append(py::make_tuple(child.first, childIndex));
            }
            nodes.append(py::make_tuple(node->term, childList));
        }

        return nodes;
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

    py::list to_serializable() const {
        return toSerializableImpl();
    }

    static BKTree from_serializable(const py::object& data) {
        BKTree tree;
        py::sequence seq = py::cast<py::sequence>(data);
        py::ssize_t length = seq.size();
        if (length <= 0) {
            return tree;
        }

        std::vector<std::shared_ptr<BKNode>> nodes;
        nodes.reserve(static_cast<std::size_t>(length));

        for (py::ssize_t i = 0; i < length; ++i) {
            py::tuple entry = py::cast<py::tuple>(seq[i]);
            std::string term = py::cast<std::string>(entry[0]);
            nodes.push_back(std::make_shared<BKNode>(term));
        }

        for (py::ssize_t i = 0; i < length; ++i) {
            py::tuple entry = py::cast<py::tuple>(seq[i]);
            py::list childList = py::cast<py::list>(entry[1]);
            for (const auto& childObj : childList) {
                py::tuple childTuple = py::cast<py::tuple>(childObj);
                int distance = py::cast<int>(childTuple[0]);
                std::size_t childIndex = py::cast<std::size_t>(childTuple[1]);
                if (childIndex >= nodes.size()) {
                    throw std::out_of_range("BKTree.from_serializable: child index out of range");
                }
                nodes[static_cast<std::size_t>(i)]->children.push_back({distance, nodes[childIndex]});
            }
        }

        tree.root = nodes.front();
        return tree;
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
           py::arg("query"), py::arg("maxdist"))
       .def("to_serializable", &BKTree::to_serializable,
           "Return a serializable representation of the BK-tree")
       .def_static("from_serializable", &BKTree::from_serializable,
           "Reconstruct a BK-tree from a serialized representation",
           py::arg("data"));
}
