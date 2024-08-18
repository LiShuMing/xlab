package main

import (
	"database/sql"
	"fmt"
	"log"
	"net/http"
	_ "net/http/pprof"
	"sync"
	"time"

	_ "github.com/go-sql-driver/mysql"
)

func main() {
	fmt.Println("vim-go")

	wg := &sync.WaitGroup{}
	// we need a webserver to get the pprof webserver
	wg.Add(1)
	go func() {
		log.Println(http.ListenAndServe("localhost:9061", nil))
	}()

	i := 0
	ch := make(chan int)
	for true {
		if i > 1 {
			break
		}
		i += 1
		wg.Add(1)
		go doOneRound(ch, wg)
	}
	for v := range ch {
		fmt.Println("receive : ", v)
	}
	// close(ch)
	wg.Wait()
	fmt.Println("BYE")
	//<-ch
}

func doOneRound(ch chan int, wg *sync.WaitGroup) {
	defer wg.Done()
	db, err := sql.Open("mysql", "root:@tcp(127.0.0.1:9131)/test")
	// db, err := sql.Open("mysql", "root:@tcp(127.0.0.1:9030)/test")
	if err != nil {
		panic(err)
	}
	db.SetConnMaxLifetime(time.Minute * 3)
	db.SetMaxOpenConns(10)
	db.SetMaxIdleConns(10)
	defer db.Close()

	i := 0
	for true {
		if i > 10 {
			break
		}
		i += 1
		doExecute(db, i, ch)
	}
}

func doExecute(db *sql.DB, i int, ch chan int) {
	// fmt.Println("start to ", i)
	// if i%2 == 0 {
	//	doQuery(db, "set follower_query_forward_mode=\"leader\";")
	// } else {
	//	doQuery(db, "set follower_query_forward_mode=\"follower\";")
	//}

	doQuery(db, "SELECT  dtstatdate as dteventtime, sum(imoney) as count FROM dws_cosgame_revenue_min_income_v2 WHERE dt IN ('2023-11-01')   AND  login_channelid = 255  AND  country_code = '255'  AND  os = 255 GROUP BY  dtstatdate ORDER BY  dtstatdate;")
	doQuery(db, "SELECT  dtstatdate as dteventtime, sum(imoney) as count FROM dws_cosgame_revenue_min_income_v2 WHERE dt IN ('2023-11-04')   GROUP BY  dtstatdate ORDER BY  dtstatdate;")
	doQuery(db, "SELECT  dtstatdate as dteventtime, sum(imoney) as count FROM dws_cosgame_revenue_min_income_v2 WHERE dt IN ('2023-11-04')   GROUP BY  dtstatdate ORDER BY  dtstatdate;")
	doQuery(db, "SELECT  dtstatdate as dteventtime, sum(imoney) as count FROM dws_cosgame_revenue_min_income_v2  GROUP BY  dtstatdate ORDER BY  dtstatdate;")
	// doQuery(db, "select * from test_shuming.t1 limit "+strconv.Itoa(i))
	ch <- i
	// close(ch)
}

func doQuery(db *sql.DB, sql string) {
	rows, err := db.Query(sql)
	if err != nil {
		panic(err.Error()) // proper error handling instead of panic in your app
	}
	doParse(rows)
}

func doParse(rows *sql.Rows) {
	// Get column names
	columns, err := rows.Columns()
	if err != nil {
		panic(err.Error()) // proper error handling instead of panic in your app
	}

	// Make a slice for the values
	values := make([]sql.RawBytes, len(columns))

	// rows.Scan wants '[]interface{}' as an argument, so we must copy the
	// references into such a slice
	// See http://code.google.com/p/go-wiki/wiki/InterfaceSlice for details
	scanArgs := make([]interface{}, len(values))
	for i := range values {
		scanArgs[i] = &values[i]
	}

	// Fetch rows
	for rows.Next() {
		// get RawBytes from data
		err = rows.Scan(scanArgs...)
		if err != nil {
			panic(err.Error()) // proper error handling instead of panic in your app
		}

		// Now do something with the data.
		// Here we just print each column as a string.
		var value string
		for i, col := range values {
			// Here we can check if the value is nil (NULL value)
			if col == nil {
				value = "NULL"
			} else {
				value = string(col)
			}
			if false {
				fmt.Println(columns[i], ": ", value)
			}
		}
		// fmt.Println("-----------------------------------")
	}
	if err = rows.Err(); err != nil {
		panic(err.Error()) // proper error handling instead of panic in your app
	}
}
