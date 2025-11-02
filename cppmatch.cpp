#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <fstream>
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
    
    std::vector<std::shared_ptr<BKNode>> collectNodes(std::unordered_map<BKNode*, std::uint32_t>& index) const {
        std::vector<std::shared_ptr<BKNode>> nodes;
        if (!root) {
            return nodes;
        }

        nodes.push_back(root);
        index[root.get()] = 0;

        for (std::size_t i = 0; i < nodes.size(); ++i) {
            const auto& node = nodes[i];
            for (const auto& child : node->children) {
                const auto& childPtr = child.second;
                if (!childPtr) {
                    continue;
                }
                auto found = index.find(childPtr.get());
                if (found == index.end()) {
                    std::uint32_t childIndex = static_cast<std::uint32_t>(nodes.size());
                    index[childPtr.get()] = childIndex;
                    nodes.push_back(childPtr);
                }
            }
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
        py::list serialized;
        std::unordered_map<BKNode*, std::uint32_t> index;
        auto nodes = collectNodes(index);

        for (std::uint32_t i = 0; i < static_cast<std::uint32_t>(nodes.size()); ++i) {
            const auto& node = nodes[i];
            py::list childList;
            for (const auto& child : node->children) {
                auto it = index.find(child.second.get());
                if (it == index.end()) {
                    throw std::runtime_error("BKTree.to_serializable: missing child index");
                }
                childList.append(py::make_tuple(child.first, it->second));
            }
            serialized.append(py::make_tuple(node->term, childList));
        }

        return serialized;
    }

    static BKTree from_serializable(const py::object& data) {
        py::sequence seq = py::cast<py::sequence>(data);
        py::ssize_t length = seq.size();
        BKTree tree;
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
            auto& nodeChildren = nodes[static_cast<std::size_t>(i)]->children;
            nodeChildren.clear();
            nodeChildren.reserve(childList.size());
            for (const auto& childObj : childList) {
                py::tuple childTuple = py::cast<py::tuple>(childObj);
                int distance = py::cast<int>(childTuple[0]);
                std::size_t childIndex = py::cast<std::size_t>(childTuple[1]);
                if (childIndex >= nodes.size()) {
                    throw std::out_of_range("BKTree.from_serializable: child index out of range");
                }
                nodeChildren.push_back({distance, nodes[childIndex]});
            }
        }

        tree.root = nodes.front();
        return tree;
    }

    void save(const std::string& path) const {
        std::ofstream out(path, std::ios::binary);
        if (!out) {
            throw std::runtime_error("BKTree.save: unable to open file for writing");
        }

        const char magic[8] = {'B', 'K', 'T', 'R', 'E', 'E', '1', 0};
        out.write(magic, sizeof(magic));

        std::unordered_map<BKNode*, std::uint32_t> index;
        auto nodes = collectNodes(index);
        std::uint32_t count = static_cast<std::uint32_t>(nodes.size());
        out.write(reinterpret_cast<const char*>(&count), sizeof(count));

        for (std::uint32_t i = 0; i < count; ++i) {
            const auto& node = nodes[i];
            std::uint32_t termLen = static_cast<std::uint32_t>(node->term.size());
            out.write(reinterpret_cast<const char*>(&termLen), sizeof(termLen));
            out.write(node->term.data(), termLen);

            std::uint32_t childCount = static_cast<std::uint32_t>(node->children.size());
            out.write(reinterpret_cast<const char*>(&childCount), sizeof(childCount));
            for (const auto& child : node->children) {
                std::uint32_t distance = static_cast<std::uint32_t>(child.first);
                auto it = index.find(child.second.get());
                if (it == index.end()) {
                    throw std::runtime_error("BKTree.save: encountered child without index");
                }
                std::uint32_t childIndex = it->second;
                out.write(reinterpret_cast<const char*>(&distance), sizeof(distance));
                out.write(reinterpret_cast<const char*>(&childIndex), sizeof(childIndex));
            }
        }
    }

    static BKTree load(const std::string& path) {
        std::ifstream in(path, std::ios::binary);
        if (!in) {
            throw std::runtime_error("BKTree.load: unable to open file for reading");
        }

        char magic[8];
        in.read(magic, sizeof(magic));
        const char expected[8] = {'B', 'K', 'T', 'R', 'E', 'E', '1', 0};
        if (!in || std::memcmp(magic, expected, sizeof(magic)) != 0) {
            throw std::runtime_error("BKTree.load: invalid file header");
        }

        std::uint32_t count = 0;
        in.read(reinterpret_cast<char*>(&count), sizeof(count));
        if (!in) {
            throw std::runtime_error("BKTree.load: failed to read node count");
        }

        std::vector<std::shared_ptr<BKNode>> nodes;
        nodes.reserve(count);
        for (std::uint32_t i = 0; i < count; ++i) {
            nodes.push_back(std::make_shared<BKNode>(std::string()));
        }

        for (std::uint32_t i = 0; i < count; ++i) {
            std::uint32_t termLen = 0;
            in.read(reinterpret_cast<char*>(&termLen), sizeof(termLen));
            if (!in) {
                throw std::runtime_error("BKTree.load: failed to read term length");
            }

            std::string term(termLen, '\0');
            if (termLen > 0) {
                in.read(&term[0], termLen);
            }
            if (!in) {
                throw std::runtime_error("BKTree.load: failed to read term data");
            }
            nodes[i]->term = std::move(term);

            std::uint32_t childCount = 0;
            in.read(reinterpret_cast<char*>(&childCount), sizeof(childCount));
            if (!in) {
                throw std::runtime_error("BKTree.load: failed to read child count");
            }

            nodes[i]->children.clear();
            nodes[i]->children.reserve(childCount);
            for (std::uint32_t c = 0; c < childCount; ++c) {
                std::uint32_t distance = 0;
                std::uint32_t childIndex = 0;
                in.read(reinterpret_cast<char*>(&distance), sizeof(distance));
                in.read(reinterpret_cast<char*>(&childIndex), sizeof(childIndex));
                if (!in) {
                    throw std::runtime_error("BKTree.load: failed to read child entry");
                }
                if (childIndex >= count) {
                    throw std::runtime_error("BKTree.load: child index out of range");
                }
                nodes[i]->children.push_back({static_cast<int>(distance), nodes[childIndex]});
            }
        }

        BKTree tree;
        tree.root = count > 0 ? nodes.front() : nullptr;
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
            "Reconstruct a BK-tree from serialized data",
            py::arg("data"))
       .def("save", &BKTree::save,
           "Serialize the BK-tree to a binary file",
           py::arg("path"))
       .def_static("load", &BKTree::load,
           "Load a BK-tree from a binary file",
           py::arg("path"));
}
