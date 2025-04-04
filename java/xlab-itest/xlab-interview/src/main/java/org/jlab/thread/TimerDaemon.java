package org.jlab.thread;

import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Timer;
import java.util.TimerTask;

public class TimerDaemon {
	private static Timer timer = new Timer(true); //定时器为守护线程

	public static void main(String[] args) {
		MyTask myTask = new MyTask();        //创建定时任务

		SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
		String dateString = "2016-01-27 22:17:10";
		try {
			Date date = sdf.parse(dateString);
			System.out.println("任务计划启动时间：" + date + "  当前时间：" + new Date());
			//			timer.schedule(myTask, date);
			// schedule task in every 1s
			timer.scheduleAtFixedRate(myTask, 1000, 1000);
			try {
				Thread.sleep(600000);
			} catch (InterruptedException e) {
				e.printStackTrace();
			}
		} catch (ParseException e) {
			e.printStackTrace();
		}
	}

	static public class MyTask extends TimerTask {
		public void run() {
			System.out.println("运行时间为：" + new Date());
		}
	}
}
