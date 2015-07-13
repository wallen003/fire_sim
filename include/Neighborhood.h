#pragma once
#include <iostream>
#include <memory>
#include <assert.h>
#include <vector>
#include <stdexcept>

using namespace std;


// Neigbors define adjecency in the Grid
class Neighborhood{
public:
    Neighborhood(size_t n, const std::vector<int>& dims, const std::vector<std::vector<long>>& offsets):
    n(n), dims(dims), offsets(offsets)
    {
        for(auto dim_offsets:offsets){
            if (dim_offsets.size() != n){
                throw exception();
            }
        }
    }
    
    const size_t n; // Number of neighbors
    const std::vector<int> dims;
    const std::vector<vector<long>> offsets; // Dimensions: [dims.size()][v]
};


//
const Neighborhood LonelyNeighboorhood(0,{},{{}});

const Neighborhood MooreNeighborhood(4,{0,1},
    {{  0, -1, 0, 1 },
     { -1,  0, 1, 0 }});

const Neighborhood VonNeumannNeighboorhood(8,{0,1},
    {{  0, -1, 0, 1, -1, -1, 1,  1 },
     { -1,  0, 1, 0, -1,  1, 1, -1 }});



