#/bin/python3

#This is a gdbinit file for StarRocks.
#This gdbinit file is used to debug StarRocks.
#It provides the following commands:
#- pcol: print the column of a pointer
#- print_query_id: print the query id of a runtime state
#
#You can source this file in your gdb by:
#source /path/to/gdbinit

import gdb
import uuid
import traceback
class Util:
    @staticmethod
    def to_query_id_string(t_unique_id):
        hi = int(t_unique_id["hi"])
        lo = int(t_unique_id["lo"])
        if hi < 0:
            hi = (1 << 64) + hi
        if lo < 0:
            lo = (1 << 64) + lo
        value = (hi << 64) | lo
        return str(uuid.UUID(int=value))

class Pcol(gdb.Command):
    def __init__(self):
        super(self.__class__, self).__init__("pcol", gdb.COMMAND_USER)

    def invoke(self, args, from_tty):
        argv = gdb.string_to_argv(args)
        ptr = argv[0]

        clazz = None
        try:
            gdb.lookup_type("starrocks::Column")
            clazz = "starrocks::Column"
        except Exception as e:
            gdb.lookup_type("starrocks::vectorized::Column")
            clazz = "starrocks::vectorized::Column"


        if ptr.startswith('0x'):
            col = gdb.parse_and_eval("*((%s*) %s)" % (clazz, ptr))
            gdb.execute('print *((%s*) %s)' % (col.dynamic_type, ptr))
            return

        col = gdb.parse_and_eval(ptr)

        if col.type.name is None and col.dynamic_type.name is None:
            col_str = col.format_string()
            if col_str.startswith('std::shared_ptr<'):
                start = len('std::shared_ptr<')
                end = col_str.find('> (use count')
                col = gdb.parse_and_eval('(std::shared_ptr<%s>)%s' % (col_str[start:end], ptr))
            else:
                gdb.execute('print %s' % col)
                return
        
        if col.dynamic_type.name.startswith('std::shared_ptr<'):
            template_type = col.dynamic_type.template_argument(0)
            gdb.execute('print %s' % ptr)
            col_ptr = gdb.parse_and_eval('%s._M_ptr' % ptr)
            col = gdb.parse_and_eval("*((%s*) %s)" % (template_type.name, col_ptr))
            gdb.execute('print *((%s*) %s)' % (col.dynamic_type, col_ptr))
Pcol()

class PrintQueryId(gdb.Function):
    def __init__(self):
        super(self.__class__, self).__init__("print_query_id")

    def invoke(self, input):
        if str(input.type) == 'starrocks::RuntimeState *':
            query_id = input.dereference()["_query_id"]
        elif str(input.type) == 'starrocks::TUniqueId':
            query_id = input
        else:
            return "not a runtime state or query id: %s" % str(input.type)

        return Util.to_query_id_string(query_id)
PrintQueryId()



import gdb
import traceback


class GetQueryContext(gdb.Function):
    """
    Get a query context from a runtime state by query id (TUniqueId string representation)
    """

    def __init__(self):
        super(GetQueryContext, self).__init__("get_query_context")

    # -------------------------
    # Utilities
    # -------------------------
    @staticmethod
    def _as_int(v):
        try:
            return int(v)
        except Exception:
            try:
                return int(v.cast(gdb.lookup_type("uintptr_t")))
            except Exception:
                return 0

    @classmethod
    def _is_null_ptr(cls, p):
        return cls._as_int(p) == 0

    @staticmethod
    def _strip_quotes(s):
        s = str(s)
        if len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
            return s[1:-1]
        return s

    @staticmethod
    def _debug(msg):
        gdb.write(msg + "\n")

    def _resolve_hashtable_nested_type(self, ht, suffix):
        ht_name = str(ht.type.strip_typedefs())
        return gdb.lookup_type(ht_name + suffix)

    def _extract_pair_from_node_type(self, node_ref):
        """
        Robustly extract pair<const Key, Mapped> from libstdc++ unordered_map node.

        node_ref layout (your case):
        - base: std::__detail::_Hash_node_base
        - base: std::__detail::_Hash_node_value<value_type, true>

        GDB sometimes fails to treat these as "base classes" cleanly, so we:
        - Try direct extraction on node_ref
        - Then try casting node_ref to EACH field's type (base or not)
        - Then try a recursive scan on those subobjects
        """

        def is_pair_like(v):
            try:
                _ = v["first"]
                _ = v["second"]
                return True
            except Exception:
                return False

        def try_extract(obj):
            # 1) direct members
            for field in ("_M_v", "_M_value"):
                try:
                    v = obj[field]
                    if is_pair_like(v):
                        return v
                except Exception:
                    pass

            # 2) aligned buffer members (very common)
            # obj._M_storage may be __aligned_buffer<value_type>
            try:
                storage = obj["_M_storage"]
                # Try _M_addr() first
                try:
                    addr = storage["_M_addr"]()
                    v = addr.dereference()
                    if is_pair_like(v):
                        return v
                except Exception:
                    pass

                # Fallback: some aligned_buffer stores raw bytes; try common internal names
                for bf in ("_M_storage", "_M_buf", "__data", "_M_data"):
                    try:
                        buf = storage[bf]
                        # Sometimes buf is an array/struct; try casting its address to value_type*
                        try:
                            vptr = buf.address.cast(gdb.lookup_type(str(obj.type.template_argument(0))).pointer())  # may fail
                            v = vptr.dereference()
                            if is_pair_like(v):
                                return v
                        except Exception:
                            pass
                    except Exception:
                        pass
            except Exception:
                pass

            # 3) scan direct named fields for pair-like
            try:
                t = obj.type.strip_typedefs()
                if t.code in (gdb.TYPE_CODE_STRUCT, gdb.TYPE_CODE_UNION):
                    for f in t.fields():
                        if not f.name:
                            continue
                        try:
                            fv = obj[f.name]
                            if is_pair_like(fv):
                                return fv
                        except Exception:
                            continue
            except Exception:
                pass

            return None

        # Fast try on node itself
        v = try_extract(node_ref)
        if v is not None:
            return v

        # Critical: attempt casting to each field's type (works for anonymous bases too)
        t = node_ref.type.strip_typedefs()
        for f in t.fields():
            try:
                ft = f.type.strip_typedefs()
            except Exception:
                continue

            # Try to view the same memory as this subobject type
            try:
                sub = node_ref.cast(ft)
            except Exception:
                continue

            v = try_extract(sub)
            if v is not None:
                self._debug("DEBUG: Extracted pair from subobject type: %s" % str(ft))
                return v

            # One more level: sometimes the value is inside *its* fields
            try:
                tt = sub.type.strip_typedefs()
                if tt.code in (gdb.TYPE_CODE_STRUCT, gdb.TYPE_CODE_UNION):
                    for f2 in tt.fields():
                        if not f2.name:
                            continue
                        try:
                            sub2 = sub[f2.name]
                            v = try_extract(sub2)
                            if v is not None:
                                self._debug("DEBUG: Extracted pair from nested field: %s.%s" %
                                            (str(ft), f2.name))
                                return v
                        except Exception:
                            continue
            except Exception:
                pass

        raise RuntimeError("Cannot locate pair value inside __node_type (even after subobject casts).")

    def _lookup_in_unordered_map(self, m, target_id_str):
        """
        Traverse std::unordered_map<TUniqueId, QueryContextPtr> using libstdc++ internals
        with hashtable nested typedefs:
        ht::__node_ptr, ht::__node_type
        This avoids RTTI and avoids guessing std::__detail::_Hash_node name.
        """
        try:
            ht = m["_M_h"]

            node_ptr_t = self._resolve_hashtable_nested_type(ht, "::__node_ptr")   # concrete node*
            node_type_t = self._resolve_hashtable_nested_type(ht, "::__node_type") # concrete node (struct)

            curr = ht["_M_before_begin"]["_M_nxt"]  # _Hash_node_base*

            while not self._is_null_ptr(curr):
                self._debug("DEBUG: Current node address: 0x%x" % self._as_int(curr))

                # Cast base pointer -> concrete node pointer
                node_ptr = curr.cast(node_ptr_t)

                # Dereference as concrete node type. Sometimes node_ptr_t already points to node_type_t.
                node_ref = node_ptr.dereference()
                # Ensure node_ref is treated as node_type_t (some typedefs may differ)
                try:
                    if node_ref.type.strip_typedefs() != node_type_t.strip_typedefs():
                        node_ref = node_ref.cast(node_type_t)
                except Exception:
                    pass

                self._debug("DEBUG: node fields: %s" % [f.name for f in node_ref.type.strip_typedefs().fields()])
                try:
                    # Cast to the second field type directly (your output显示第二个就是 _Hash_node_value<...>)
                    ft = node_ref.type.strip_typedefs().fields()[1].type.strip_typedefs()
                    sub = node_ref.cast(ft)
                    self._debug("DEBUG: subobject[1] type: %s" % str(ft))
                    self._debug("DEBUG: subobject[1] fields: %s" % [x.name for x in ft.fields()])
                except Exception as e:
                    self._debug("DEBUG: subobject[1] inspect failed: %s" % str(e))
                pair_val = self._extract_pair_from_node_type(node_ref)

                unique_id = pair_val["first"]
                ctx_ptr = pair_val["second"]

                current_id_str = Util.to_query_id_string(unique_id)
                self._debug("DEBUG: Current ID string: %s" % current_id_str)

                if current_id_str == target_id_str:
                    return ctx_ptr

                # Next pointer: available via base layout; easiest is to read from node_ref (inherits base)
                # If that fails, fall back to curr.dereference() as base.
                try:
                    curr = node_ref["_M_nxt"]
                except Exception:
                    curr = curr.dereference()["_M_nxt"]

        except Exception as e:
            self._debug("DEBUG: Manual map traversal failed: %s" % str(e))
            # import traceback; traceback.print_exc()

        return None

    # -------------------------
    # GDB function entry
    # -------------------------
    def invoke(self, runtime_state, query_id):
        # Normalize runtime_state to pointer
        rs = runtime_state
        rs_type_str = str(rs.type)

        if rs_type_str.endswith("&"):
            rs = rs.referenced_value()
            rs_type_str = str(rs.type)

        if not rs_type_str.endswith("*"):
            try:
                rs = rs.address
                rs_type_str = str(rs.type)
            except Exception:
                return "not a runtime state pointer: %s" % str(runtime_state.type)

        if "RuntimeState" not in rs_type_str:
            return "not a runtime state pointer: %s" % rs_type_str

        query_id_str = self._strip_quotes(query_id)

        # Access ExecEnv -> QueryContextManager -> context_maps
        try:
            rs_obj = rs.dereference()
            exec_env = rs_obj["_exec_env"]
            if self._is_null_ptr(exec_env):
                return "exec_env is null"

            query_context_mgr = exec_env.dereference()["_query_context_mgr"]
            if self._is_null_ptr(query_context_mgr):
                return "query_context_mgr is null"

            context_maps = query_context_mgr.dereference()["_context_maps"]
        except Exception as e:
            return "Failed to access internal structures: %s" % str(e)

        # Iterate std::vector<unordered_map<...>>
        try:
            impl = context_maps["_M_impl"]
            start = impl["_M_start"]
            finish = impl["_M_finish"]

            count = int(finish - start)
            self._debug("DEBUG: Vector size: %d" % count)

            for i in range(count):
                u_map = start[i]
                res = self._lookup_in_unordered_map(u_map, query_id_str)
                if res is not None and not self._is_null_ptr(res):
                    return res

        except Exception as e:
            self._debug("DEBUG: Vector iteration failed: %s" % str(e))
            return "Vector iteration failed: %s" % str(e)

        return "QueryContext not found for ID: %s" % query_id_str
GetQueryContext()


import gdb


class GetFragmentContext(gdb.Function):
    """
    Get a fragment context from a query context by fragment instance id (TUniqueId string representation)
    Usage:
      (gdb) p $get_fragment_context(query_context_ptr, "fragment-instance-id-string")
    """

    def __init__(self):
        super(GetFragmentContext, self).__init__("get_fragment_context")

    # -------------------------
    # Utilities
    # -------------------------
    @staticmethod
    def _as_int(v):
        try:
            return int(v)
        except Exception:
            try:
                return int(v.cast(gdb.lookup_type("uintptr_t")))
            except Exception:
                return 0

    @classmethod
    def _is_null_ptr(cls, p):
        return cls._as_int(p) == 0

    @staticmethod
    def _strip_quotes(s):
        s = str(s)
        if len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
            return s[1:-1]
        return s

    @staticmethod
    def _debug(msg):
        gdb.write(msg + "\n")

    def _unique_ptr_get(self, up):
        """
        Extract raw pointer from libstdc++ std::unique_ptr<T> in a RTTI/pretty-printer independent way.

        unique_ptr layout (libstdc++):
        up._M_t (a __uniq_ptr_impl<...> base) contains:
            _M_t : std::tuple<T*, Deleter>

        tuple layout:
        std::_Tuple_impl<0, T*, Deleter> inherits
            std::_Head_base<0, T*, false> { T* _M_head_impl; }
            std::_Head_base<1, Deleter, true> { Deleter _M_head_impl; }

        Accessing _M_head_impl is ambiguous unless we cast to the correct _Head_base<0,...>.
        """
        # Step 1: get the inner tuple object (try several field paths, but no tuple indexing)
        tup = None
        # Common: up._M_t._M_t  (your pretty-print shows this)
        try:
            tup = up["_M_t"]["_M_t"]
        except Exception:
            pass
        if tup is None:
            try:
                # sometimes one more nesting
                tup = up["_M_t"]["_M_t"]["_M_t"]
            except Exception:
                pass
        if tup is None:
            # last resort: try directly
            try:
                tup = up["_M_t"]
            except Exception:
                pass
        if tup is None:
            raise RuntimeError("Cannot reach unique_ptr internal tuple (_M_t).")

        # Step 2: build the exact Head_base<0, T*, false> type name and cast
        # We need T from unique_ptr<T>.
        up_t = up.type.strip_typedefs()
        try:
            # unique_ptr<T, D> => template_argument(0) is T
            pointee_t = up_t.template_argument(0)
        except Exception:
            raise RuntimeError("Cannot resolve unique_ptr<T> template argument.")

        head0_name = "std::_Head_base<0, %s, false>" % str(pointee_t.pointer())
        try:
            head0_t = gdb.lookup_type(head0_name)
        except Exception as e:
            raise RuntimeError("Cannot lookup type %s: %s" % (head0_name, str(e)))

        try:
            head0 = tup.cast(head0_t)
            p = head0["_M_head_impl"]
            if p.type.code == gdb.TYPE_CODE_PTR and not self._is_null_ptr(p):
                return p
        except Exception as e:
            raise RuntimeError("Failed to extract pointer via Head_base<0>: %s" % str(e))

        raise RuntimeError("unique_ptr extracted pointer is null or not a pointer.")
    # -------------------------
    # Hashtable nested typedef resolver
    # -------------------------
    def _resolve_hashtable_nested_type(self, ht, suffix):
        ht_name = str(ht.type.strip_typedefs())
        return gdb.lookup_type(ht_name + suffix)

    # -------------------------
    # Node value extraction (pair<const Key, Mapped>)
    # -------------------------
    def _is_pair_like(self, v):
        try:
            _ = v["first"]
            _ = v["second"]
            return True
        except Exception:
            return False

    def _try_extract_pair_from_obj(self, obj):
        # Common in libstdc++ node value base:
        for field in ("_M_v", "_M_value"):
            try:
                v = obj[field]
                if self._is_pair_like(v):
                    return v
            except Exception:
                pass

        # aligned buffer: _M_storage._M_addr() -> value_type*
        try:
            storage = obj["_M_storage"]
            try:
                addr = storage["_M_addr"]()
                v = addr.dereference()
                if self._is_pair_like(v):
                    return v
            except Exception:
                pass
        except Exception:
            pass

        # Direct named scan (sometimes works if fields are named)
        try:
            t = obj.type.strip_typedefs()
            if t.code in (gdb.TYPE_CODE_STRUCT, gdb.TYPE_CODE_UNION):
                for f in t.fields():
                    if not f.name:
                        continue
                    try:
                        fv = obj[f.name]
                        if self._is_pair_like(fv):
                            return fv
                    except Exception:
                        continue
        except Exception:
            pass

        return None

    def _extract_pair_from_node_type(self, node_ref):
        """
        Extract pair<const Key, Mapped> from libstdc++ unordered_map node.

        Primary: try known layouts (_M_v / _M_storage).
        Fallback: scan node memory for a value_type that looks like a pair (first/second accessible).
        """

        def is_pair_like(v):
            try:
                _ = v["first"]
                _ = v["second"]
                return True
            except Exception:
                return False

        def try_extract(obj):
            for field in ("_M_v", "_M_value"):
                try:
                    v = obj[field]
                    if is_pair_like(v):
                        return v
                except Exception:
                    pass

            try:
                storage = obj["_M_storage"]
                try:
                    addr = storage["_M_addr"]()
                    v = addr.dereference()
                    if is_pair_like(v):
                        return v
                except Exception:
                    pass
            except Exception:
                pass

            return None

        # 1) direct try
        v = try_extract(node_ref)
        if v is not None:
            return v

        # 2) try subobjects by casting to each field type (covers some anonymous bases)
        t = node_ref.type.strip_typedefs()
        for f in t.fields():
            try:
                ft = f.type.strip_typedefs()
                sub = node_ref.cast(ft)
            except Exception:
                continue
            v = try_extract(sub)
            if v is not None:
                self._debug("DEBUG: Extracted pair from subobject type: %s" % str(ft))
                return v

        # 3) HARD fallback: scan raw memory for value_type
        # value_type is ht::value_type == std::pair<const Key, Mapped>
        try:
            # node_ref is __node_type; it should have a typedef for __value_type in hashtable,
            # but easiest is: infer from node_ref by asking hashtable value_type in caller.
            # Here, we reconstruct from node_ref by searching for a pair type name in debug info.
            # We'll require caller to set self._cached_value_type before calling this function.
            value_type = self._cached_value_type
        except Exception:
            raise RuntimeError("Missing self._cached_value_type for memory-scan fallback.")

        value_type = self._cached_value_type
        value_ptr_t = value_type.pointer()
        base = node_ref.address.cast(gdb.lookup_type("char").pointer())

        for off in range(0, 512, 8):
            try:
                cand = (base + off).cast(value_ptr_t).dereference()
                if is_pair_like(cand):
                    self._debug("DEBUG: Found pair by memory scan at offset %d" % off)
                    return cand
            except Exception:
                continue

        raise RuntimeError("Cannot locate pair value inside __node_type (and memory scan failed).")

    # -------------------------
    # unordered_map traversal
    # -------------------------
    def _lookup_in_unordered_map(self, m, target_id_str):
        """
        Traverse std::unordered_map<TUniqueId, FragmentContextPtr>.
        """
        try:
            ht = m["_M_h"]

            ht_name = str(ht.type.strip_typedefs())
            try:
                self._cached_value_type = gdb.lookup_type(ht_name + "::__value_type")
            except Exception:
                # Fallback: some libstdc++ use value_type instead of __value_type
                self._cached_value_type = gdb.lookup_type(ht_name + "::value_type")
            self._debug("DEBUG: cached value_type=%s" % str(self._cached_value_type))

            node_ptr_t = self._resolve_hashtable_nested_type(ht, "::__node_ptr")
            node_type_t = self._resolve_hashtable_nested_type(ht, "::__node_type")

            curr = ht["_M_before_begin"]["_M_nxt"]  # _Hash_node_base*

            while not self._is_null_ptr(curr):
                self._debug("DEBUG: Current node address: 0x%x" % self._as_int(curr))

                node_ptr = curr.cast(node_ptr_t)
                node_ref = node_ptr.dereference()

                # Normalize to node_type_t if possible
                try:
                    if node_ref.type.strip_typedefs() != node_type_t.strip_typedefs():
                        node_ref = node_ref.cast(node_type_t)
                except Exception:
                    pass

                self._debug("DEBUG: node_type=%s" % str(node_ref.type.strip_typedefs()))
                self._debug("DEBUG: node fields: %s" % [str(x.type.strip_typedefs()) for x in node_ref.type.strip_typedefs().fields()])
                self._debug("DEBUG: cached value_type=%s" % str(getattr(self, "_cached_value_type", None)))

                pair_val = self._extract_pair_from_node_type(node_ref)

                unique_id = pair_val["first"]
                ctx_ptr = pair_val["second"]

                current_id_str = Util.to_query_id_string(unique_id)
                self._debug("DEBUG: Current fragment ID string: %s" % current_id_str)

                if current_id_str == target_id_str:
                    return ctx_ptr

                # Next pointer: available in base
                try:
                    curr = node_ref["_M_nxt"]
                except Exception:
                    curr = curr.dereference()["_M_nxt"]

        except Exception as e:
            self._debug("DEBUG: Manual map traversal failed: %s" % str(e))

        return None

    # -------------------------
    # GDB function entry
    # -------------------------
    def invoke(self, query_context, fragment_id):
        """
        Get FragmentContext from QueryContext by fragment_instance_id.
        """
        qc = query_context
        qc_type_str = str(qc.type)
        self._debug("DEBUG: QueryContext type: %s" % qc_type_str)

        if qc_type_str.endswith("&"):
            qc = qc.referenced_value()
            qc_type_str = str(qc.type)

        if not qc_type_str.endswith("*"):
            try:
                qc = qc.address
                qc_type_str = str(qc.type)
            except Exception:
                return "not a query context pointer: %s" % str(query_context.type)

        if "QueryContext" not in qc_type_str:
            return "not a query context pointer: %s" % qc_type_str

        fragment_id_str = self._strip_quotes(fragment_id)

        # Access QueryContext::_fragment_mgr (unique_ptr) -> FragmentContextManager::_fragment_contexts (unordered_map)
        try:
            qc_obj = qc.dereference()

            fragment_mgr_up = qc_obj["_fragment_mgr"]

            raw_mgr_ptr = self._unique_ptr_get(fragment_mgr_up)
            self._debug("DEBUG: FragmentContextManager* = 0x%x" % self._as_int(raw_mgr_ptr))

            if self._is_null_ptr(raw_mgr_ptr):
                return "fragment_mgr is null"

            # Validate it's really FragmentContextManager* by checking field existence
            try:
                mgr_obj = raw_mgr_ptr.dereference()
                fragment_contexts = mgr_obj["_fragment_contexts"]
            except Exception as e:
                return "unique_ptr raw pointer does not look like FragmentContextManager*: %s" % str(e)

        except Exception as e:
            self._debug("DEBUG: Access failed: %s" % str(e))
            return "Failed to access fragment_mgr/_fragment_contexts: %s" % str(e)

        # Lookup
        try:
            result = self._lookup_in_unordered_map(fragment_contexts, fragment_id_str)
            if result is not None and not self._is_null_ptr(result):
                return result
        except Exception as e:
            self._debug("DEBUG: Fragment context lookup failed: %s" % str(e))
            return "Fragment context lookup failed: %s" % str(e)

        return "FragmentContext not found for ID: %s" % fragment_id_str
GetFragmentContext()