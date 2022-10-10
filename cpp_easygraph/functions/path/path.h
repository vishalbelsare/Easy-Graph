#pragma once
#define BOOST_PYTHON_STATIC_LIB

#include "../../common/common.h"

py::object _dijkstra_multisource(py::object G, py::object sources, py::object weight, py::object target);
py::object Floyd(py::object G);
py::object Prim(py::object G);
py::object Kruskal(py::object G);